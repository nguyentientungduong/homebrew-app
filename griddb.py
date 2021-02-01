import requests
import re
from requests.auth import HTTPBasicAuth

from redash.query_runner import BaseSQLQueryRunner, register
from redash.utils import json_dumps

from redash.query_runner import TYPE_STRING, TYPE_DATETIME, TYPE_INTEGER, TYPE_FLOAT, TYPE_BOOLEAN

TYPES_MAP = {
    'STRING': TYPE_STRING,
    'BOOL': TYPE_BOOLEAN,
    'BYTE': TYPE_INTEGER,
    'SHORT': TYPE_INTEGER,
    'INTEGER': TYPE_INTEGER,
    'LONG': TYPE_INTEGER,
    'FLOAT': TYPE_FLOAT,
    'DOUBLE': TYPE_FLOAT,
    'TIMESTAMP': TYPE_DATETIME,
    'GEOMETRY': TYPE_STRING,
    'BLOB': TYPE_STRING,
    'STRING_ARRAY': TYPE_STRING,
    'BOOL_ARRAY': TYPE_STRING,
    'BYTE_ARRAY': TYPE_STRING,
    'SHORT_ARRAY': TYPE_STRING,
    'INTEGER_ARRAY': TYPE_STRING,
    'LONG_ARRAY': TYPE_STRING,
    'FLOAT_ARRAY': TYPE_STRING,
    'DOUBLE_ARRAY': TYPE_STRING,
    'TIMESTAMP_ARRAY': TYPE_STRING
}


class GridDB(BaseSQLQueryRunner):
    # Configuration for adding new datasource
    @classmethod
    def configuration_schema(cls):
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string"
                },
                "port": {
                    "type": "number"
                },
                "cluster": {
                    "type": "string"
                },
                "database": {
                    "type": "string"
                },
                "username": {
                    "type": "string"
                },
                "password": {
                    "type": "string"
                }
            },
            "required": ["host", "port", "cluster", "database", "username", "password"],
            "order": ["host", "port", "cluster", "database", "username", "password"],
            "secret": ["password"]
        }

    @classmethod
    def type(cls):
        return "griddb"

    @classmethod
    def name(cls):
        return "GridDB"

    def test_connection(self):
        host = self.configuration['host']
        port = self.configuration['port']
        cluster = self.configuration['cluster']
        database = self.configuration['database']
        username = self.configuration['username']
        password = self.configuration['password']
        headers = {'Content-Type': 'application/json'}
        url = 'http://' + str(host) + ':' + str(port) + '/griddb/v2/' + str(cluster) + '/dbs/' + str(database) + '/checkConnection'
        response = requests.get(url, headers=headers, auth=HTTPBasicAuth(username, password))
        if response.status_code != 200:
            raise Exception("Failed to connect to database.")

    # Execute TQL
    def run_query(self, query, user):
        host = self.configuration['host']
        port = self.configuration['port']
        cluster = self.configuration['cluster']
        database = self.configuration['database']
        username = self.configuration['username']
        password = self.configuration['password']

        # Send request to WebAPI
        url = 'http://' + str(host) + ':' + str(port) + '/griddb/v2/' + str(cluster) + '/dbs/' + str(database) + '/tql'
        headers = {'Content-Type': 'application/json'}
        body = []
        gw_tql_input = {}

        # Extract container name from query
        pattern = r'from\s+(\w+).*'
        container_names = re.findall(pattern, query, re.IGNORECASE)
        container_name = container_names[0]
        gw_tql_input['name'] = container_name
        gw_tql_input['stmt'] = query
        body.append(gw_tql_input)
        response = requests.post(url, headers=headers, auth=HTTPBasicAuth(username, password), json=body)
        if response.status_code == 200:
            columns = self.fetch_columns([(i[u'name'], TYPES_MAP.get(i[u'type'], None)) for i in response.json()[0]['columns']])
            rows_raw = response.json()[0]['results']
            rows = [dict(zip((c['name'] for c in columns), row)) for row in rows_raw]

            data = {'columns': columns, 'rows': rows}
            json_data = json_dumps(data)
            error = None
        else:
            json_data = None
            error = response.json()['errorMessage']

        return json_data, error

    # Get schema of all containers
    def _get_tables(self, schema):
        host = self.configuration['host']
        port = self.configuration['port']
        cluster = self.configuration['cluster']
        database = self.configuration['database']
        username = self.configuration['username']
        password = self.configuration['password']
        headers = {'Content-Type': 'application/json'}

        # Maximum total containers
        maximum_total_containers = 5000

        # Get list of containers
        get_list_containers_url = 'http://' + str(host) + ':' + str(port) + '/griddb/v2/' + str(cluster) + '/dbs/' + database + '/containers/'
        get_list_containers_response = requests.get(get_list_containers_url, headers=headers, auth=HTTPBasicAuth(username, password), params={'limit': maximum_total_containers})
        if get_list_containers_response.status_code == 200:
            list_containers = get_list_containers_response.json()['names']
        else:
            raise Exception("Failed getting list of containers.")

        for container in list_containers:
            # Get container info of each container
            url = 'http://' + str(host) + ':' + str(port) + '/griddb/v2/' + cluster + '/dbs/' + database + '/containers/' + container + '/info'
            response = requests.get(url, headers=headers, auth=HTTPBasicAuth(username, password))
            if response.status_code == 200:
                container_info = {}
                container_name = response.json()['container_name']
                container_info['name'] = container_name
                list_columns = []
                for column in response.json()['columns']:
                    list_columns.append(column['name'])
                container_info['columns'] = list_columns
                schema[container_name] = container_info
            else:
                raise Exception("Failed getting schema.")

        return schema.values()


register(GridDB)
