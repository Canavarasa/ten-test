import re
from web3 import Web3
from ten.test.basetest import GenericNetworkTest
from ten.test.contracts.error import Error
from ten.test.helpers.ws_proxy import WebServerProxy


class PySysTest(GenericNetworkTest):
    PROXY = False

    def execute(self):
        network = self.get_network_connection()
        web3, account = network.connect_account1(self, web_socket=True)

        # go through a proxy to log websocket communications (don't think the proxy works on Ten
        # due to params in the url so need to investigate
        if self.PROXY:
            ws_url = WebServerProxy.create(self).run(network.connection_url(web_socket=True), 'proxy.logs')
            web3 = Web3(Web3.WebsocketProvider(ws_url, websocket_timeout=120))

        error = Error(self, web3)
        error.deploy(network, account)

        # force a require
        try:
            self.log.info('Forcing a require on contract function')
            error.contract.functions.force_require().call()
        except Exception as e:
            self.log.info('Exception type: %s', type(e).__name__)
            self.log.info('Exception args: %s', e.args)
            regex = re.compile('execution reverted:.*Forced require', re.M)
            self.assertTrue(regex.search(e.args[0]) is not None)

        # force a revert
        try:
            self.log.info('Forcing a revert on contract function')
            error.contract.functions.force_revert().call()
        except Exception as e:
            self.log.info('Exception type: %s', type(e).__name__)
            self.log.info('Exception args: %s', e.args)
            regex = re.compile('execution reverted:.*Forced revert', re.M)
            self.assertTrue(regex.search(e.args[0]) is not None)

        # force assert
        try:
            self.log.info('Forcing an assert on contract function')
            error.contract.functions.force_assert().call()
        except Exception as e:
            self.log.info('Exception type: %s', type(e).__name__)
            self.log.info('Exception args: %s', e.args)
            regex = re.compile('execution reverted', re.M)
            self.assertTrue(regex.search(e.args[0]) is not None)