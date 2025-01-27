import re
from pysys.constants import FAILED, PASSED
from web3.exceptions import TimeExhausted
from ten.test.basetest import GenericNetworkTest
from ten.test.contracts.gas import GasConsumerBalance


class PySysTest(GenericNetworkTest):

    def execute(self):
        network = self.get_network_connection()
        web3, account = network.connect_account1(self)

        contract = GasConsumerBalance(self, web3)
        contract.deploy(network, account)

        est_1 = contract.contract.functions.get_balance().estimate_gas()
        self.log.info("Estimate get_balance:    %d", est_1)

        nonce = self.nonce_db.get_next_nonce(self, web3, account.address, self.env, persist_nonce=False)
        build_tx = contract.contract.functions.get_balance().buildTransaction(
            {
                'nonce': nonce,
                'gasPrice': web3.eth.gas_price, # the price we are willing to pay per gas unit (dimension is gwei)
                'gas': int(est_1 / 2),          # max gas units prepared to pay (dimension is computational units)
                'chainId': web3.eth.chain_id
            }
        )
        signed_tx = account.sign_transaction(build_tx)
        try:
            tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            if not self.is_ten():
                self.addOutcome(FAILED, 'Exception should be thrown')
            else:
                self.log.info('Transaction sent with hash %s', tx_hash.hex())
                try:
                    web3.eth.wait_for_transaction_receipt(tx_hash.hex(), timeout=30)
                except TimeExhausted as e:
                    self.log.warn("'Transaction timed out as expected")
                    self.addOutcome(PASSED, 'Exception should be thrown')

        except Exception as e:
            self.log.error('Exception type: %s', type(e))
            self.log.error('Exception message: %s', e.args[0]['message'])
            regex = re.compile('intrinsic gas too low', re.M)
            self.assertTrue(regex.search(e.args[0]['message']) is not None)


