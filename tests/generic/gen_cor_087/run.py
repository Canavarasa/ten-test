import os
from obscuro.test.basetest import GenericNetworkTest
from obscuro.test.contracts.storage import KeyStorage
from obscuro.test.networks.factory import NetworkFactory
from obscuro.test.utils.properties import Properties
from obscuro.test.helpers.ws_proxy import WebServerProxy


class PySysTest(GenericNetworkTest):

    def execute(self):
        # connect to network
        network = NetworkFactory.get_network(self)
        web3, account = network.connect_account1(self)

        # deploy the contract
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
        args.extend(['--network_ws', ws_url])
        args.extend(['--address', '%s' % storage.address])
        args.extend(['--contract_abi', '%s' % storage.abi_path])
        args.extend(['--filter_key', 'k1'])
        self.run_javascript(script, stdout, stderr, args)
        self.waitForGrep(file=stdout, expr='Starting task ...', timeout=10)

        # perform some transactions with a sleep in between
        network.transact(self, web3, storage.contract.functions.setItem('k1', 1), account, storage.GAS_LIMIT)
        network.transact(self, web3, storage.contract.functions.setItem('foo', 2), account, storage.GAS_LIMIT)
        network.transact(self, web3, storage.contract.functions.setItem('bar', 3), account, storage.GAS_LIMIT)
        network.transact(self, web3, storage.contract.functions.setItem('k2', 4), account, storage.GAS_LIMIT)
        network.transact(self, web3, storage.contract.functions.setItem('k2', 5), account, storage.GAS_LIMIT)
        network.transact(self, web3, storage.contract.functions.setItem('k1', 6), account, storage.GAS_LIMIT)
        self.wait(float(self.block_time) * 1.1)

        # wait and validate
        self.waitForGrep(file=stdout, expr='Stored value = 6', timeout=20)
        expr_list = ['Stored value = 1', 'Stored value = 6']
        self.assertOrderedGrep(file=stdout, exprList=expr_list)

        # validate correct count if duplicates are not allowed
        if not self.ALLOW_EVENT_DUPLICATES:
            self.assertLineCount(file=stdout, expr='Stored value = [0-9]$', condition='== 2')
