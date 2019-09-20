'''Client for connection with Gaia machines'''
import requests


class GaiaClient(object):
    """docstring for Client"""

    def __init__(self, address, user=None, pwd=None):
        if user and pwd:
            self.requests = requests.Session()

            self.requests.post(address + "/login", json={"user": user, "password": pwd})

        else:
            self.requests = requests


        self.applications = {}
        self.address = address
        # Get applications
        applications_json = self.requests.get(self.address + '/api/applications').json()
        entities = self._get_entities(applications_json)

        for entity in entities:
            self.applications[entity['properties']['name']] = self._get_actions(entity)

    def state(self):
        '''Returns state of gaia machine'''
        return self.requests.get(self.address + '/api').json()['properties']['state']

    def _get_entities(self, json):
        '''Fetch entities from Siren entry'''

        entities = []
        for i in json['entities']:
            entities.append(i)
        return entities

    def _get_actions(self, entity):

        actions = {}

        entity_details = self.requests.get(entity['href']).json()

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
                request = self.requests.post(
                    json=fields, url=action['href'], headers={'Content-type': action['type']}
                )
                # TODO: Handle error nicely
                request.raise_for_status()

            return post_func

        else:
            def get_func():
                '''Get function'''
                request = self.requests.get(url=action['href'], headers={'Content-type': action['type']})
                # TODO: Handle error nicely
                request.raise_for_status()
                return request

            return get_func



'''
g = GaiaClient("http://192.168.133.130:1234")

# This is how output is set
g.applications['SlideLockCtrl_OUT']['set-ON']()

# and this is stateful application
g.applications['BatteryConnector']['set-Work']()

# Robot tool change
g.applications['MainRobot']['changeTo-FingerBase']()
'''
