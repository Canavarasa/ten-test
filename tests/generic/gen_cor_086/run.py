import os, time
from obscuro.test.obscuro_test import ObscuroTest
from obscuro.test.contracts.storage.key_storage import KeyStorage
from obscuro.test.networks.factory import NetworkFactory
from obscuro.test.utils.properties import Properties
from obscuro.test.helpers.ws_proxy import WebServerProxy


class PySysTest(ObscuroTest):

    def execute(self):
        # connect to network
        network = NetworkFactory.get_network(self.env)
        web3, account = network.connect_account1(self)

        # deploy the contract and dump out the abi
        storage = KeyStorage(self, web3)
        storage.deploy(network, account)

        # go through a proxy to log websocket communications if needed
        ws_url = network.connection_url(web_socket=True)
        if self.PROXY: ws_url = WebServerProxy.create(self).run(ws_url, 'proxy.logs')

        # run a background script to filter and collect events
        stdout = os.path.join(self.output, 'listener.out')
        stderr = os.path.join(self.output, 'listener.err')
        script = os.path.join(self.input, 'listener.js')
        args = []
        args.extend(['--network_http', '%s' % network.connection_url(web_socket=False)])
        args.extend(['--network_ws', ws_url])
        args.extend(['--contract_address', '%s' % storage.contract_address])
        args.extend(['--contract_abi', '%s' % storage.abi_path])
        args.extend(['--filter_value', '2'])
        args.extend(['--filter_key', 'k2'])
        if self.is_obscuro(): args.extend(['--pk_to_register', '%s' % Properties().account3pk()])
        self.run_javascript(script, stdout, stderr, args)
        self.waitForGrep(file=stdout, expr='Starting task ...', timeout=10)

        # perform some transactions with a sleep in between
        network.transact(self, web3, storage.contract.functions.setItem('k1', 1), account, storage.GAS)
        network.transact(self, web3, storage.contract.functions.setItem('foo', 2), account, storage.GAS)
        network.transact(self, web3, storage.contract.functions.setItem('bar', 3), account, storage.GAS)
        network.transact(self, web3, storage.contract.functions.setItem('k2', 4), account, storage.GAS)
        network.transact(self, web3, storage.contract.functions.setItem('r1', 5), account, storage.GAS)
        network.transact(self, web3, storage.contract.functions.setItem('r2', 2), account, storage.GAS)
        self.wait(float(self.block_time) * 1.1)

        # wait and validate
        self.waitForGrep(file=stdout, expr='stored value = [0-9]$', condition='== 3', timeout=20)

        # contract.filters.ItemSet1(options.filter_key, null) - key is k2
        expr_list = ['ItemSet1, stored value = 4']
        self.assertOrderedGrep(file=stdout, exprList=expr_list)

        # contract.filters.ItemSet2(null, options.filter_value) - value is 2
        expr_list = ['ItemSet2, stored value = 2', 'ItemSet2, stored value = 2']
        self.assertOrderedGrep(file=stdout, exprList=expr_list)
