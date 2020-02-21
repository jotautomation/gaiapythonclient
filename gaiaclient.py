'''Client for connecting with Gaia machines'''
import threading
import json
import requests
import websocket


class Client:
    '''Client for connecting with Gaia machines'''

    def __init__(
            self,
            address,
            user=None,
            pwd=None,
            machine_state_callback=None,
            wait_ready_event=None,
            wait_closing_event=None,
            wait_not_ready_event=None
    ):

        if user and pwd:
            self.requests = requests.Session()

            self.requests.post(address + "/login", json={"user": user, "password": pwd})

        else:
            self.requests = requests

        def on_error(ws, error):
            '''Handle error'''
            print(error)

        def on_message(ws, message):
            '''Handle state change messages'''
            try:
                message = json.loads(message)
                if machine_state_callback:
                    machine_state_callback(message)

                if wait_ready_event:
                    if message['state'] == 'Ready':
                        wait_ready_event.set()
                    else:
                        wait_ready_event.clear()

                if wait_not_ready_event:
                    if message['state'] == 'Ready':
                        wait_not_ready_event.clear()
                    else:
                        wait_not_ready_event.set()

                if wait_closing_event:
                    if message['state'] == 'Closing' or message['state'] == 'Ready':
                        wait_closing_event.set()
                    else:
                        wait_closing_event.clear()

            except Exception as e:
                print(e)

        state_socket = websocket.WebSocketApp(
            "ws://" + address.strip("http://") + "/websocket/state", on_message=on_message
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

        return 'Ready' in self.state

    @property
    def test_box_closing(self):
        '''Returns true if test box is test box is closing

        When test box is closing some tests may be executed. Note that
        on this case test box is not RF or audio shielded. Also because
        of safety reasons robot is not powered'''
        return 'Closing' in self.state

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

                # Fields thats value is defined in API. "Static" fields.
                fields = {}
                for field in action['fields']:
                    if 'value' in field:
                        fields[field['name']] = field['value']

                # User defined fields. "Variable" fields
                fields.update(kwargs)
                request = self.requests.post(
                    json=fields, url=action['href'], headers={'Content-type': action['type']}
                )
                # TODO: Handle error nicely
                request.raise_for_status()

            return post_func

        else:

            def get_func():
                '''Get function'''
                request = self.requests.get(
                    url=action['href'], headers={'Content-type': action['type']}
                )
                # TODO: Handle error nicely
                request.raise_for_status()
                return request

            return get_func
