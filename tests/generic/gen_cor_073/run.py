import os
from obscuro.test.basetest import GenericNetworkTest
from obscuro.test.contracts.storage import Storage
from obscuro.test.networks.factory import NetworkFactory
from obscuro.test.helpers.ws_proxy import WebServerProxy


class PySysTest(GenericNetworkTest):

    def execute(self):
        # connect to network
        network = NetworkFactory.get_network(self)
        web3, account = network.connect_account1(self)

        # deploy the contract
        storage = Storage(self, web3, 100)
        storage.deploy(network, account)

        # go through a proxy to log websocket communications if needed
        ws_url = network.connection_url(web_socket=True)
        if self.PROXY: ws_url = WebServerProxy.create(self).run(ws_url, 'proxy.logs')

        # run a background script to filter and collect events
        stdout = os.path.join(self.output, 'poller.out')
        stderr = os.path.join(self.output, 'poller.err')
        script = os.path.join(self.input, 'poller.js')
        args = []
        args.extend(['--network_ws', ws_url])
        args.extend(['--address', '%s' % storage.address])
        args.extend(['--contract_abi', '%s' % storage.abi_path])
        self.run_javascript(script, stdout, stderr, args)
        self.waitForGrep(file=stdout, expr='Starting task ...', timeout=10)

        # perform some transactions with a sleep in between
        for i in range(0,5):
            network.transact(self, web3, storage.contract.functions.store(i), account, storage.GAS_LIMIT)
        self.wait(float(self.block_time) * 1.1)

        # wait and validate
        self.waitForGrep(file=stdout, expr='Stored value = 4', timeout=20)
        self.assertOrderedGrep(file=stdout, exprList=['Stored value = %d' % x for x in range(0, 5)])

        # validate correct count
        self.assertLineCount(file=stdout, expr='Stored value', condition='== 5')
