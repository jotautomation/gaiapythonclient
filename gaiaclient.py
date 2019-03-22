'''Client for connecting with Gaia machines'''
import requests


class Client(object):
    '''Client for connecting with Gaia machines'''

    def __init__(self, address):

        self._applications = {}
        self.address = address
        # Get applications
        applications_json = requests.get(self.address + '/api/applications').json()
        entities = self._get_entities(applications_json)

        for entity in entities:
            self._applications[entity['properties']['name']] = {
                'actions': self._get_actions(entity),
                'properties': entity['properties'],
            }

        root_json = requests.get(self.address + '/api').json()

        self.state_triggers = self._get_actions(root_json)

    @property
    def state(self):
        '''Returns state of gaia machine'''
        return requests.get(self.address + '/api').json()['properties']['state']

    @property
    def applications(self):
        '''Returns all available applications'''
        return self._applications

    @property
    def ready_for_testing(self):
        '''Returns true if test box is fully available for all tests'''

        return 'Executing' in self.state

    @property
    def test_box_closing(self):
        '''Returns true if test box is test box is closing

        When test box is closing some tests may be executed. Note that
        on this case test box is not RF or audio shielded. Also because
        of safety reasons robot is not powered'''
        return 'Active_ClosingTestBox' in self.state

    def _get_entities(self, json):
        '''Fetch entities from Siren entry'''

        entities = []
        for i in json['entities']:
            entities.append(i)
        return entities

    def _get_actions(self, entity):

        actions = {}

        entity_details = requests.get(entity['href']).json()

        for action in entity_details['actions']:
            actions[action['name']] = self._get_fields(action)

        # Add also blocked actions
        if 'blockedActions' in entity_details:
            for action in entity_details['blockedActions']:
                actions[action['name']] = self._get_fields(action)

        return actions

    def _get_fields(self, action):
        if action['method'] == 'POST':

            def post_func():
                '''Post function'''
                fields = {}
                for field in action['fields']:
                    if 'value' in field:
                        fields[field['name']] = field['value']
                request = requests.post(
                    json=fields, url=action['href'], headers={'Content-type': action['type']}
                )
                # TODO: Handle error nicely
                request.raise_for_status()

            return post_func

        else:

            def get_func():
                '''Get function'''
                request = requests.get(
                    url=action['href'], headers={'Content-type': action['type']}
                )
                # TODO: Handle error nicely
                request.raise_for_status()
                return request

            return get_func
