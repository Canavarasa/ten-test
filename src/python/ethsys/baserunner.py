import os, time, shutil, sys
from pysys.constants import PROJECT, BACKGROUND
from pysys.exceptions import AbortExecution
from ethsys.utils.process import Processes
from ethsys.networks.ganache import Ganache
from ethsys.networks.obscuro import Obscuro
from ethsys.utils.properties import Properties


class EthereumRunnerPlugin():

    def setup(self, runner):
        """Set up a runner plugin to start any processes required to execute the tests."""
        environment = 'obscuro' if runner.mode is None else runner.mode
        runner.log.info('Runner is executing against environment %s' % environment)

        self.output = os.path.join(PROJECT.root, '.runner')
        if os.path.exists(self.output): shutil.rmtree(self.output)
        os.makedirs(self.output)

        try:
            if environment == 'obscuro':
                self.run_wallets(runner, 'testnet.obscu.ro')
            elif environment == 'obscuro.dev':
                self.run_wallets(runner, 'dev-testnet.obscu.ro')
            elif environment == 'obscuro.local':
                self.run_wallets(runner, '127.0.0.1')
            elif environment == 'ganache':
                self.run_ganache(runner)
        except AbortExecution as e:
            runner.log.info('Error executing runner plugin startup actions', e)
            runner.log.info('See contents of the .runner directory in the project root for any process output')
            runner.log.info('Exiting ...')
            runner.cleanup()
            sys.exit()

    def run_ganache(self, runner):
        """RUn ganache for use by the tests. """
        stdout = os.path.join(self.output, 'ganache.out')
        stderr = os.path.join(self.output, 'ganache.err')

        arguments = []
        arguments.extend(('--port', str(Ganache.PORT)))
        arguments.extend(('--account', '0x%s,1000000000000000000' % Properties().account1pk()))
        arguments.extend(('--account', '0x%s,1000000000000000000' % Properties().account2pk()))
        arguments.extend(('--account', '0x%s,1000000000000000000' % Properties().account3pk()))
        arguments.extend(('--gasLimit', '7200000'))
        hprocess = runner.startProcess(command=Processes.get_ganache_bin(), displayName='ganache',
                                       workingDir=self.output , environs=os.environ, quiet=True,
                                       arguments=arguments, stdout=stdout, stderr=stderr, state=BACKGROUND)

        runner.waitForSignal(stdout, expr='Listening on 127.0.0.1:%d' % Ganache.PORT, timeout=30)
        runner.addCleanupFunction(lambda: self.__stop_process(hprocess))

    def run_wallets(self, runner, host):
        """Run wallet extensions for use by the tests. """
        self.run_wallet(runner, host, Obscuro.ACCOUNT1_PORT)
        self.run_wallet(runner, host, Obscuro.ACCOUNT2_PORT)
        self.run_wallet(runner, host, Obscuro.ACCOUNT3_PORT)
        time.sleep(1)

    def run_wallet(self, runner, host, port):
        """Run a single wallet extension for use by the tests. """
        runner.log.info('Starting wallet extension on %s %d' % (host, port))
        stdout = os.path.join(self.output, 'wallet_%d.out' % port)
        stderr = os.path.join(self.output, 'wallet_%d.err' % port)

        arguments = []
        arguments.extend(('--nodeHost', host))
        arguments.extend(('--nodePortHTTP', '13000'))
        arguments.extend(('--nodePortWS', '13001'))
        arguments.extend(('--port', str(port)))
        arguments.extend(('--portWS', str(port+1)))
        arguments.extend(('--logPath', os.path.join(self.output, 'wallet_%d_logs.txt' % port)))
        hprocess = runner.startProcess(command=os.path.join(PROJECT.root, 'artifacts', 'wallet_extension'),
                                       displayName='wallet_extension', workingDir=self.output , environs=os.environ,
                                       quiet=True, arguments=arguments, stdout=stdout, stderr=stderr, state=BACKGROUND)
        runner.waitForSignal(stdout, expr='Wallet extension started', timeout=30)
        runner.addCleanupFunction(lambda: self.__stop_process(hprocess))

    def __stop_process(self, hprocess):
        """Stop a process started by this runner plugin."""
        hprocess.stop()