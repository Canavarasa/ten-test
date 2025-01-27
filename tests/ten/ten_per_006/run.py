import secrets, os, math, time
from datetime import datetime
from collections import OrderedDict
from web3 import Web3
from pysys.constants import FAILED
from ten.test.contracts.storage import Storage
from ten.test.basetest import TenNetworkTest
from ten.test.utils.gnuplot import GnuplotHelper


class PySysTest(TenNetworkTest):
    ITERATIONS = 10
    CLIENTS = 5
    DURATION = 120
    ESTIMATE = True

    def transact(self, network_connection, web3, storage, count, account, gas_limit):
        start_time = time.perf_counter()
        tx_receipt = network_connection.transact(self, web3, storage.contract.functions.store(count), account,
                                                 gas_limit, estimate=self.ESTIMATE)
        end_time = time.perf_counter()
        gas_used = tx_receipt['gasUsed']
        self.log.info('Gas used for the transaction is %d', gas_used)
        return gas_used, (end_time - start_time)

    def __init__(self, descriptor, outsubdir, runner):
        super().__init__(descriptor, outsubdir, runner)
        self.clients = []

    def execute(self):
        # connect to the network
        network = self.get_network_connection()
        web3, account = network.connect_account1(self)

        # deploy the contract
        storage = Storage(self, web3, 0)
        storage.deploy(network, account)

        # do a sanity check and break hard if the network is slow
        times = []
        gas_limit = storage.GAS_LIMIT
        for i in range(0, self.ITERATIONS):
            gas_used, time = self.transact(network, web3, storage, 0, account, gas_limit)
            times.append(time)
            gas_limit = gas_used
        avg = (sum(times) / len(times))
        self.log.info('Average latency for %d transactions is %.2f', self.ITERATIONS, avg)
        if avg > 10.0: self.addOutcome(FAILED, outcomeReason='Average latency %.2f is greater than 10 seconds' % avg)

        # run some concurrent clients, bin the latency and plot the results
        if self.DURATION > 0:
            self.log.info('')
            self.log.info('Starting all concurrent clients')
            for i in range(0, self.CLIENTS): self.storage_client(storage.address, storage.abi_path, i, network)
            for i in range(0, self.CLIENTS): self.waitForGrep(file='client_%d.out' % i, expr='Client running', timeout=10)
            self.wait(self.DURATION)
            self.log.info('Stopping all concurrent clients')
            for client in self.clients: client.stop()
            self.graph()

    def storage_client(self, address, abi_path, num, network):
        pk = secrets.token_hex(32)
        account = Web3().eth.account.privateKeyToAccount(pk)
        self.distribute_native(account, 0.01)
        network.connect(self, private_key=pk, check_funds=False)

        stdout = os.path.join(self.output, 'client_%d.out' % num)
        stderr = os.path.join(self.output, 'client_%d.err' % num)
        script = os.path.join(self.input, 'storage_client.py')
        args = []
        args.extend(['--network_http', '%s' % network.connection_url()])
        args.extend(['--address', '%s' % address])
        args.extend(['--contract_abi', '%s' % abi_path])
        args.extend(['--pk_to_register', '%s' % pk])
        args.extend(['--output_file', 'client_%s.log' % num])
        self.clients.append(self.run_python(script, stdout, stderr, args))

    def graph(self):
        # load the latency values and sort
        l = []
        for i in range(0, self.CLIENTS):
            with open(os.path.join(self.output, 'client_%d.log' % i), 'r') as fp:
                for line in fp.readlines(): l.append(float(line.strip()))
        l.sort()
        self.log.info('Average latency = %.2f', (sum(l) / len(l)))
        self.log.info('Median latency = %.2f', l[int(len(l) / 2)])

        # bin into intervals and write to file
        bins = OrderedDict()
        bin_inc = 20  # 0.05 intervals
        bin = lambda x: int(math.floor(bin_inc*x))

        for i in range(bin(l[0]), bin(l[len(l)-1])+1): bins[i] = 0
        for v in l: bins[bin(v)] = bins[bin(v)] + 1
        with open(os.path.join(self.output, 'bins.log'), 'w') as fp:
            for k in bins.keys(): fp.write('%.2f %d\n' % (k/float(bin_inc), bins[k]))
            fp.flush()

        # plot out the results
        branch = GnuplotHelper.buildInfo().branch
        date = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        GnuplotHelper.graph(self, os.path.join(self.input, 'gnuplot.in'),
                            branch, date,
                            str(self.mode), str(len(l)), str(self.DURATION), '%d' % self.CLIENTS)
