'''Client for connecting with Gaia machines'''
import threading
import json
import requests
import websocket
import queue


class Client:
    '''Client for connecting with Gaia machines'''

    def __init__(self, address, user=None, pwd=None, machine_state_callback=None):
        def prependurl(url):
            return url if "://" in url else "http://" + url

        address = prependurl(address)

        self.app_wait_list = []
        self.app_wait_list_lock = threading.Lock()

        # Threading event for waiting that the test box is started to close
        self.wait_closing_event = threading.Event()

        # Threading event for waiting that the test box is ready for testing
        self.wait_ready_event = threading.Event()

        # Threading event for waiting that the test box is not ready for testing
        self.wait_not_ready_event = threading.Event()

        if user and pwd:
            self.requests = requests.Session()

            self.requests.post(address + "/login", json={"user": user, "password": pwd})

        else:
            self.requests = requests

        def on_error(ws, error):
            '''Handle error'''
            print(error)

        def on_status_message(ws, message):
            '''Handle state change messages'''
            try:
                message = json.loads(message)
                if machine_state_callback:
                    machine_state_callback(message)

                if message['state'] == 'Ready':
                    self.wait_ready_event.set()
                    self.wait_not_ready_event.clear()
                else:
                    self.wait_ready_event.clear()
                    self.wait_not_ready_event.set()

                if message['state'] == 'Closing' or message['state'] == 'Ready':
                    self.wait_closing_event.set()
                else:
                    self.wait_closing_event.clear()

            except Exception as e:
                print(e)

        state_socket = websocket.WebSocketApp(
            "ws://" + address.strip("http://") + "/websocket/state", on_message=on_status_message
        )

        state_socket_thread = threading.Thread(target=state_socket.run_forever)
        state_socket_thread.setDaemon(True)
        state_socket_thread.start()

        def on_app_message(ws, message):
            '''Handle application state change messages'''
            try:
                message = json.loads(message)

                with self.app_wait_list_lock:
                    remove_these = []
                    for app in self.app_wait_list:
                        if app['name'] == message['name']:
                            if message['value'] in app['state']:
                                app['resolved_state'].put(message['value'])
                                app['wait_event'].set()
                                remove_these.append(app)

                    for item in remove_these:
                        self.app_wait_list.remove(item)

            except Exception as e:
                import logging

                logging.basicConfig(level=logging.DEBUG)
                logger = logging.getLogger(__name__)
                logger.exception(e)

        state_socket = websocket.WebSocketApp(
            "ws://" + address.strip("http://") + "/websocket/applications",
            on_message=on_app_message,
        )

        state_socket_thread = threading.Thread(target=state_socket.run_forever)
        state_socket_thread.setDaemon(True)
        state_socket_thread.start()

        self._applications = {}
        self.address = address

        # Get applications
        applications_json = self.requests.get(self.address + '/api/applications').json()
        entities = self._get_entities(applications_json)

        for entity in entities:
            if entity['properties']['name'] in self._applications:
                if entity['properties']['alias']:
                    self._applications[entity['properties']['alias']] = {
                        'actions': self._get_actions(entity),
                        'properties': entity['properties'],
                    }
            else:
                self._applications[entity['properties']['name']] = {
                    'actions': self._get_actions(entity),
                    'properties': entity['properties'],
                }

        root_json = self.requests.get(self.address + '/api').json()

        self.state_triggers = self._get_actions(root_json)

    @property
    def state(self):
        '''Returns state of gaia machine'''
        return self.requests.get(self.address + '/api').json()['properties']['state']

    @property
    def properties(self):
        '''Returns properties of gaia machine'''
        return self.requests.get(self.address + '/api').json()['properties']

    @property
    def applications(self):
        '''Returns all available applications'''
        return self._applications

    @property
    def ready_for_testing(self):
        '''Returns true if test box is fully available for all tests'''

        return self.state == 'Ready'

    @property
    def test_box_closing(self):
        '''Returns true if test box is test box is closing

        When test box is closing some tests may be executed. Note that
        on this case test box is not RF or audio shielded. Also because
        of safety reasons robot is not powered'''
        return self.state == 'Closing' or self.ready_for_testing

    def set_app_state(self, name, state, sync=True, timeout=None):
        """Convenience method to set stateful application state.

        Calls internally application action and waits that the state
        is reached (if sync arg is true).

        Args:
            name: The name of the application.
            state: The state that must be reached.
            sync: If true, execution stops on this method until the application is
                on the wanted state, the application goes to the error or timeout
                is reached.
            timeout: Maximum time to wait. TimeoutError will be raised if timeout
                   is reached. Omitted if sync is False.

        Raises:
            TimeoutError: The application didn't reach the wanted state within the timeout time.
            ApplicationError: The application went to error state
        """
        self.applications[name]['actions']['set-' + state]()
        if sync:
            self.wait_app_state(name, state)

    def run_main_robot(self, gcode, sync=True, prerun_timeout=10):
        """Convenience method to run G-CODE/CNC on main robot.

        Calls internally application action and waits that the ready state
        is reached (if sync arg is true).

        Args:
            name: The name of the application.
            state: The state that must be reached.
            sync: If true, execution stops on this method until the application is
                on the wanted state, the application goes to the error or timeout
                is reached.
            prerun_timeout: Maximum time to wait for robot to be ready before starting new cnc run.
                          TimeoutError will be raised if timeout is reached.
                          Omitted if sync is False.

        Raises:
            TimeoutError: The application didn't reach the wanted state within the timeout time.
            ApplicationError: The application went to error state
        """

        # Wait that the robot is ready
        self.wait_app_state('MainRobot', 'Ready', prerun_timeout)

        # Get wait event for active state
        active_wait, resolved_state = self.app_wait_event('MainRobot', 'Active_CncMode_Busy', True)

        self.applications["MainRobot"]['actions']["cnc_run"](plain_text=gcode)

        # Wait that the main robot reaches the active state
        Client._handle_app_state_wait(
            active_wait, resolved_state, 3, 'Active_CncMode_Busy', 'MainRobot'
        )

        if sync:
            # Wait that the cnc run is done
            self.wait_app_state('MainRobot', 'Ready')

    def app_wait_event(self, name, state, stop_wait_on_error=False):
        '''Returns thread.event that can be used to wait application state change'''

        wait_event = threading.Event()

        states = [state]
        resolved_state = queue.Queue()

        if stop_wait_on_error:
            states.extend(['error', 'Error', 'ErrorState'])
        current_state = self.applications[name]['properties']['state']
        if current_state in states:
            resolved_state.put(current_state)
            wait_event.set()
        else:
            with self.app_wait_list_lock:
                self.app_wait_list.append(
                    {
                        'name': name,
                        'state': states,
                        'wait_event': wait_event,
                        'resolved_state': resolved_state,
                    }
                )

        return wait_event, resolved_state

    def wait_app_state(self, name, state, timeout=None):
        """Stops execution until the application is on the wanted state.

        Args:
            name: The name of the application.
            state: The state that must be reached.
            timeout: Maximum time to wait. TimeoutError will be raised if timeout
                   is reached.

        Raises:
            TimeoutError: The application didn't reach the wanted state within the timeout time.
            ApplicationError: The application went to error state
        """
        wait_event, resolved_state = self.app_wait_event(name, state, True)
        Client._handle_app_state_wait(wait_event, resolved_state, timeout, state, name)

    @staticmethod
    def _handle_app_state_wait(wait_event, resolved_state, timeout, state, name):
        if not wait_event.wait(timeout):
            raise TimeoutError(
                "Timeout while waiting for the state '{}' for the application '{}'".format(
                    state, name
                )
            )

        if resolved_state.empty():
            return

        current_state = resolved_state.get()
        if current_state != state:
            raise ApplicationError(
                "The application '{}' waiting for the state '{}' went to state '{}'".format(
                    name, state, current_state
                )
            )

    def wait_ready(self, timeout=None):
        """Waits that the tester is ready and available for all tests.
        Timeout on seconds. Returns True if there was no timeout."""

        if self.ready_for_testing:
            return True

        return self.wait_ready_event.wait(timeout)

    def wait_closing(self, timeout=None):
        """Waits that the tester is closing.
        Timeout on seconds. Returns True if there was no timeout."""

        if self.test_box_closing:
            return True

        return self.wait_closing_event.wait(timeout)

    def wait_not_ready(self, timeout=None):
        """Waits that the tester is not ready.
        Timeout on seconds. Returns True if there was no timeout."""

        if not self.ready_for_testing:
            return True

        return self.wait_not_ready_event.wait(timeout)

    def _get_entities(self, json):
        '''Fetch entities from Siren entry'''

        entities = []
        for i in json['entities']:
            entities.append(i)
        return entities

    def _get_actions(self, entity):

        actions = {}
        try:
            entity_details = self.requests.get(entity['href']).json()
        except Exception as e:
            print(entity)

        for action in entity_details['actions']:
            actions[action['name']] = self._get_fields(action)
        # Add also blocked actions
        if 'blocked_actions' in entity_details:
            for action in entity_details['blocked_actions']:
                actions[action['name']] = self._get_fields(action)

        return actions

    def _get_fields(self, action):
        if action['method'] == 'POST':

            def post_func(**kwargs):
                '''Post function'''

                if 'plain_text' in kwargs.keys():
                    response = self.requests.post(
                        data=kwargs['plain_text'],
                        url=action['href'],
                        headers={'Content-type': action['type']},
                    )
                else:
                    # Fields thats value is defined in API. "Static" fields.
                    fields = {}
                    for field in action['fields']:
                        if 'value' in field:
                            fields[field['name']] = field['value']

                    # User defined fields. "Variable" fields
                    fields.update(kwargs)
                    response = self.requests.post(
                        json=fields, url=action['href'], headers={'Content-type': action['type']}
                    )
                if response.status_code != 200:
                    raise GaiaError(response.text)

                response.raise_for_status()

            return post_func

        else:

            def get_func():
                '''Get function'''
                response = self.requests.get(
                    url=action['href'], headers={'Content-type': action['type']}
                )
                if response.status_code != 200:
                    raise GaiaError(response.text)

                response.raise_for_status()
                return response

            return get_func


# define Python user-defined exceptions
class GaiaError(Exception):
    """Generic Gaia error and base class for other exceptions"""

    pass


class TimeoutError(GaiaError):
    """Raised when timeout occurs"""

    pass


class ApplicationError(GaiaError):
    """Raised when the application is on error state"""

    pass
