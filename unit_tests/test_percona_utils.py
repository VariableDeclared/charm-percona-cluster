import os
import unittest
import sys
import tempfile

import mock

sys.modules['MySQLdb'] = mock.Mock()
import percona_utils

from test_utils import CharmTestCase

os.environ['JUJU_UNIT_NAME'] = 'percona-cluster/2'


class UtilsTests(unittest.TestCase):
    def setUp(self):
        super(UtilsTests, self).setUp()

    @mock.patch("percona_utils.log")
    def test_update_empty_hosts_file(self, mock_log):
        map = {'1.2.3.4': 'my-host'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            percona_utils.HOSTS_FILE = tmpfile.name
            percona_utils.HOSTS_FILE = tmpfile.name
            percona_utils.update_hosts_file(map)

        with open(tmpfile.name, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "%s %s\n" % (map.items()[0]))

    @mock.patch("percona_utils.log")
    def test_update_hosts_file_w_dup(self, mock_log):
        map = {'1.2.3.4': 'my-host'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            percona_utils.HOSTS_FILE = tmpfile.name

            with open(tmpfile.name, 'w') as fd:
                fd.write("%s %s\n" % (map.items()[0]))

            percona_utils.update_hosts_file(map)

        with open(tmpfile.name, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "%s %s\n" % (map.items()[0]))

    @mock.patch("percona_utils.log")
    def test_update_hosts_file_entry(self, mock_log):
        altmap = {'1.1.1.1': 'alt-host'}
        map = {'1.1.1.1': 'hostA',
               '2.2.2.2': 'hostB',
               '3.3.3.3': 'hostC',
               '4.4.4.4': 'hostD'}
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            percona_utils.HOSTS_FILE = tmpfile.name

            with open(tmpfile.name, 'w') as fd:
                fd.write("#somedata\n")
                fd.write("%s %s\n" % (altmap.items()[0]))

            percona_utils.update_hosts_file(map)

        with open(percona_utils.HOSTS_FILE, 'r') as fd:
            lines = fd.readlines()

        os.remove(tmpfile.name)
        self.assertEqual(len(lines), 5)
        self.assertEqual(lines[0], "#somedata\n")
        self.assertEqual(lines[1], "%s %s\n" % (map.items()[0]))
        self.assertEqual(lines[4], "%s %s\n" % (map.items()[3]))

    @mock.patch("percona_utils.get_cluster_host_ip")
    @mock.patch("percona_utils.log")
    @mock.patch("percona_utils.config")
    @mock.patch("percona_utils.update_hosts_file")
    @mock.patch("percona_utils.relation_get")
    @mock.patch("percona_utils.related_units")
    @mock.patch("percona_utils.relation_ids")
    def test_get_cluster_hosts(self, mock_rel_ids, mock_rel_units,
                               mock_rel_get,
                               mock_update_hosts_file, mock_config,
                               mock_log,
                               mock_get_cluster_host_ip):
        mock_rel_ids.return_value = [1]
        mock_rel_units.return_value = [2]
        mock_get_cluster_host_ip.return_value = '10.2.0.1'

        def _mock_rel_get(*args, **kwargs):
            return {'private-address': '10.2.0.2'}

        mock_rel_get.side_effect = _mock_rel_get
        mock_config.side_effect = lambda k: False

        hosts = percona_utils.get_cluster_hosts()

        self.assertFalse(mock_update_hosts_file.called)
        mock_rel_get.assert_called_with(rid=1, unit=2)
        self.assertEqual(hosts, ['10.2.0.1', '10.2.0.2'])

    @mock.patch.object(percona_utils, 'socket')
    @mock.patch("percona_utils.get_cluster_host_ip")
    @mock.patch.object(percona_utils, 'get_ipv6_addr')
    @mock.patch.object(percona_utils, 'log')
    @mock.patch.object(percona_utils, 'config')
    @mock.patch.object(percona_utils, 'update_hosts_file')
    @mock.patch.object(percona_utils, 'relation_get')
    @mock.patch.object(percona_utils, 'related_units')
    @mock.patch.object(percona_utils, 'relation_ids')
    def test_get_cluster_hosts_ipv6(self, mock_rel_ids, mock_rel_units,
                                    mock_rel_get,
                                    mock_update_hosts_file, mock_config,
                                    mock_log, mock_get_ipv6_addr,
                                    mock_get_cluster_host_ip,
                                    mock_socket):
        ipv6addr = '2001:db8:1:0:f816:3eff:fe79:cd'
        mock_get_ipv6_addr.return_value = [ipv6addr]
        mock_rel_ids.return_value = [88]
        mock_rel_units.return_value = [1, 2]
        mock_get_cluster_host_ip.return_value = 'hostA'
        mock_socket.gethostname.return_value = 'hostA'

        def _mock_rel_get(*args, **kwargs):
            host_suffix = 'BC'
            id = kwargs.get('unit')
            hostname = "host{}".format(host_suffix[id - 1])
            return {'private-address': '10.0.0.{}'.format(id + 1),
                    'hostname': hostname}

        config = {'prefer-ipv6': True}
        mock_rel_get.side_effect = _mock_rel_get
        mock_config.side_effect = lambda k: config.get(k)

        hosts = percona_utils.get_cluster_hosts()

        mock_update_hosts_file.assert_called_with({ipv6addr: 'hostA',
                                                   '10.0.0.2': 'hostB',
                                                   '10.0.0.3': 'hostC'})
        mock_rel_get.assert_has_calls([mock.call(rid=88, unit=1),
                                       mock.call(rid=88, unit=2)])
        self.assertEqual(hosts, ['hostA', 'hostB', 'hostC'])

    @mock.patch.object(percona_utils, 'get_address_in_network')
    @mock.patch.object(percona_utils, 'log')
    @mock.patch.object(percona_utils, 'config')
    @mock.patch.object(percona_utils, 'relation_get')
    @mock.patch.object(percona_utils, 'related_units')
    @mock.patch.object(percona_utils, 'relation_ids')
    def test_get_cluster_hosts_w_cluster_network(self, mock_rel_ids,
                                                 mock_rel_units,
                                                 mock_rel_get,
                                                 mock_config,
                                                 mock_log,
                                                 mock_get_address_in_network):
        mock_rel_ids.return_value = [88]
        mock_rel_units.return_value = [1, 2]
        mock_get_address_in_network.return_value = '10.100.0.1'

        def _mock_rel_get(*args, **kwargs):
            host_suffix = 'BC'
            unit = kwargs.get('unit')
            hostname = "host{}".format(host_suffix[unit - 1])
            return {'private-address': '10.0.0.{}'.format(unit + 1),
                    'cluster-address': '10.100.0.{}'.format(unit + 1),
                    'hostname': hostname}

        config = {'cluster-network': '10.100.0.0/24'}
        mock_rel_get.side_effect = _mock_rel_get
        mock_config.side_effect = lambda k: config.get(k)

        hosts = percona_utils.get_cluster_hosts()
        mock_rel_get.assert_has_calls([mock.call(rid=88, unit=1),
                                       mock.call(rid=88, unit=2)])
        self.assertEqual(hosts, ['10.100.0.1', '10.100.0.2', '10.100.0.3'])

    @mock.patch.object(percona_utils, 'is_leader')
    @mock.patch.object(percona_utils, 'related_units')
    @mock.patch.object(percona_utils, 'relation_ids')
    @mock.patch.object(percona_utils, 'config')
    def test_is_sufficient_peers(self, mock_config, mock_relation_ids,
                                 mock_related_units, mock_is_leader):
        mock_is_leader.return_value = False
        _config = {'min-cluster-size': None}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertTrue(percona_utils.is_sufficient_peers())

        mock_is_leader.return_value = False
        mock_relation_ids.return_value = ['cluster:0']
        mock_related_units.return_value = ['test/0']
        _config = {'min-cluster-size': 3}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertFalse(percona_utils.is_sufficient_peers())

        mock_is_leader.return_value = False
        mock_related_units.return_value = ['test/0', 'test/1']
        _config = {'min-cluster-size': 3}
        mock_config.side_effect = lambda key: _config.get(key)
        self.assertTrue(percona_utils.is_sufficient_peers())

    @mock.patch.object(percona_utils, 'lsb_release')
    def test_packages_eq_wily(self, mock_lsb_release):
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': 'wily'}
        self.assertEqual(percona_utils.determine_packages(),
                         ['percona-xtradb-cluster-server'])

    @mock.patch.object(percona_utils, 'lsb_release')
    def test_packages_gt_wily(self, mock_lsb_release):
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': 'xenial'}
        self.assertEqual(percona_utils.determine_packages(),
                         ['percona-xtradb-cluster-server'])

    @mock.patch.object(percona_utils, 'lsb_release')
    def test_packages_lt_wily(self, mock_lsb_release):
        mock_lsb_release.return_value = {'DISTRIB_CODENAME': 'trusty'}
        self.assertEqual(percona_utils.determine_packages(),
                         ['percona-xtradb-cluster-server-5.5',
                          'percona-xtradb-cluster-client-5.5'])

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_not_ready(self, _wsrep_value):
        _wsrep_value.side_effect = [None, None]
        self.assertFalse(percona_utils.cluster_in_sync())

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_ready_syncing(self, _wsrep_value):
        _wsrep_value.side_effect = [True, None]
        self.assertFalse(percona_utils.cluster_in_sync())

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_ready_sync(self, _wsrep_value):
        _wsrep_value.side_effect = [True, 4]
        self.assertTrue(percona_utils.cluster_in_sync())

    @mock.patch.object(percona_utils, 'get_wsrep_value')
    def test_cluster_in_sync_ready_sync_donor(self, _wsrep_value):
        _wsrep_value.side_effect = [True, 2]
        self.assertTrue(percona_utils.cluster_in_sync())

    @mock.patch("percona_utils.config")
    def test_get_wsrep_provider_options(self, mock_config):
        # Empty
        _config = {"min-cluster-size": 3}
        mock_config.side_effect = lambda key: _config.get(key)
        expected = ""
        self.assertEqual(percona_utils.get_wsrep_provider_options(),
                         expected)

        # IPv6 only
        _config = {"prefer-ipv6": True}
        mock_config.side_effect = lambda key: _config.get(key)
        expected = "gmcast.listen_addr=tcp://:::4567"
        self.assertEqual(percona_utils.get_wsrep_provider_options(),
                         expected)
        # ipv6 and peer_timeout
        _config = {"peer-timeout": "PT15S",
                   "prefer-ipv6": True}
        mock_config.side_effect = lambda key: _config.get(key)
        expected = ("gmcast.listen_addr=tcp://:::4567;"
                    "gmcast.peer_timeout=PT15S")
        self.assertEqual(percona_utils.get_wsrep_provider_options(),
                         expected)

        # peer_timeout bad setting
        _config = {"peer-timeout": "10"}
        mock_config.side_effect = lambda key: _config.get(key)
        with self.assertRaises(ValueError):
            percona_utils.get_wsrep_provider_options()
        _config = {"peer-timeout": "PT10M"}
        mock_config.side_effect = lambda key: _config.get(key)
        with self.assertRaises(ValueError):
            percona_utils.get_wsrep_provider_options()


TO_PATCH = [
    'is_sufficient_peers',
    'is_bootstrapped',
    'config',
    'cluster_in_sync',
    'is_leader',
    'related_units',
    'relation_ids',
    'relation_get',
    'leader_get',
    'is_unit_paused_set',
    'is_clustered',
    'distributed_wait',
]


class UtilsTestsCTC(CharmTestCase):
    def setUp(self):
        CharmTestCase.setUp(self, percona_utils, TO_PATCH)

    def test_single_unit(self):
        self.config.return_value = None
        self.is_sufficient_peers.return_value = True
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'active'

    def test_insufficient_peers(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = False
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'blocked'

    def test_not_bootstrapped(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = False
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'waiting'

    def test_bootstrapped_in_sync(self):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = True
        self.cluster_in_sync.return_value = True
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'active'

    @mock.patch('time.sleep', return_value=None)
    def test_bootstrapped_not_in_sync(self, mock_time):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = True
        self.cluster_in_sync.return_value = False
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'blocked'

    @mock.patch('time.sleep', return_value=None)
    def test_bootstrapped_not_in_sync_to_synced(self, mock_time):
        self.config.return_value = 3
        self.is_sufficient_peers.return_value = True
        self.is_bootstrapped.return_value = True
        self.cluster_in_sync.side_effect = [False, False, True]
        stat, _ = percona_utils.charm_check_func()
        assert stat == 'active'

    @mock.patch.object(percona_utils, 'pxc_installed')
    @mock.patch.object(percona_utils, 'determine_packages')
    @mock.patch.object(percona_utils, 'application_version_set')
    @mock.patch.object(percona_utils, 'get_upstream_version')
    def test_assess_status(self, get_upstream_version,
                           application_version_set,
                           determine_packages,
                           pxc_installed):
        get_upstream_version.return_value = '5.6.17'
        determine_packages.return_value = ['percona-xtradb-cluster-server-5.6']
        pxc_installed.return_value = True
        with mock.patch.object(percona_utils, 'assess_status_func') as asf:
            callee = mock.Mock()
            asf.return_value = callee
            percona_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()
            get_upstream_version.assert_called_with(
                'percona-xtradb-cluster-server-5.6'
            )
            application_version_set.assert_called_with('5.6.17')

    @mock.patch.object(percona_utils, 'pxc_installed')
    @mock.patch.object(percona_utils, 'determine_packages')
    @mock.patch.object(percona_utils, 'application_version_set')
    @mock.patch.object(percona_utils, 'get_upstream_version')
    def test_assess_status_find_pkg(self, get_upstream_version,
                                    application_version_set,
                                    determine_packages,
                                    pxc_installed):
        get_upstream_version.side_effect = [None, None, '5.6.17']
        determine_packages.return_value = ['percona-xtradb-cluster-server']
        pxc_installed.return_value = True
        with mock.patch.object(percona_utils, 'assess_status_func') as asf:
            callee = mock.Mock()
            asf.return_value = callee
            percona_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()
            get_upstream_version.assert_called_with(
                'percona-xtradb-cluster-server-5.6'
            )
            application_version_set.assert_called_with('5.6.17')

    @mock.patch.object(percona_utils, 'log')
    @mock.patch.object(percona_utils, 'pxc_installed')
    @mock.patch.object(percona_utils, 'determine_packages')
    @mock.patch.object(percona_utils, 'application_version_set')
    @mock.patch.object(percona_utils, 'get_upstream_version')
    def test_assess_status_find_pkg_fails(self, get_upstream_version,
                                          application_version_set,
                                          determine_packages,
                                          pxc_installed, log):
        get_upstream_version.return_value = None
        determine_packages.return_value = ['percona-xtradb-cluster-server']
        pxc_installed.return_value = True
        with mock.patch.object(percona_utils, 'assess_status_func') as asf:
            callee = mock.Mock()
            asf.return_value = callee
            percona_utils.assess_status('test-config')
            asf.assert_called_once_with('test-config')
            callee.assert_called_once_with()
            get_upstream_version.assert_called_with(
                'percona-xtradb-cluster-server-5.7'
            )
            self.assertFalse(application_version_set.called)
            self.assertTrue(log.called)

    @mock.patch.object(percona_utils, 'services')
    @mock.patch.object(percona_utils, 'REQUIRED_INTERFACES')
    @mock.patch.object(percona_utils, 'make_assess_status_func')
    def test_assess_status_func(self,
                                make_assess_status_func,
                                REQUIRED_INTERFACES,
                                services):
        services.return_value = ['mysql']
        percona_utils.assess_status_func('test-config')
        # ports=None whilst port checks are disabled.
        make_assess_status_func.assert_called_once_with(
            'test-config', REQUIRED_INTERFACES, charm_func=mock.ANY,
            services=['mysql'], ports=None)
        services.assert_called_once()

    def test_pause_unit_helper(self):
        with mock.patch.object(percona_utils, '_pause_resume_helper') as prh:
            percona_utils.pause_unit_helper('random-config')
            prh.assert_called_once_with(percona_utils.pause_unit,
                                        'random-config')
        with mock.patch.object(percona_utils, '_pause_resume_helper') as prh:
            percona_utils.resume_unit_helper('random-config')
            prh.assert_called_once_with(percona_utils.resume_unit,
                                        'random-config')

    @mock.patch.object(percona_utils, 'services')
    def test_pause_resume_helper(self, services):
        f = mock.Mock()
        services.return_value = 's1'
        with mock.patch.object(percona_utils, 'assess_status_func') as asf:
            asf.return_value = 'assessor'
            percona_utils._pause_resume_helper(f, 'some-config')
            asf.assert_called_once_with('some-config')
            # ports=None whilst port checks are disabled.
            f.assert_called_once_with('assessor', services='s1', ports=None)

    @mock.patch.object(percona_utils, 'is_sufficient_peers')
    def test_cluster_ready(self, mock_is_sufficient_peers):

        # Not sufficient number of peers
        mock_is_sufficient_peers.return_value = False
        self.assertFalse(percona_utils.cluster_ready())

        # Not all cluster ready
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = False
        _config = {'min-cluster-size': 3}
        self.config.side_effect = lambda key: _config.get(key)
        self.assertFalse(percona_utils.cluster_ready())

        # All cluster ready
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = 'UUID'
        _config = {'min-cluster-size': 3}
        self.config.side_effect = lambda key: _config.get(key)
        self.assertTrue(percona_utils.cluster_ready())

        # Not all cluster ready no min-cluster-size
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = False
        _config = {'min-cluster-size': None}
        self.config.side_effect = lambda key: _config.get(key)
        self.assertFalse(percona_utils.cluster_ready())

        # All cluster ready no min-cluster-size
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = 'UUID'
        _config = {'min-cluster-size': None}
        self.config.side_effect = lambda key: _config.get(key)
        self.assertTrue(percona_utils.cluster_ready())

        # Assume single unit no-min-cluster-size
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = []
        self.related_units.return_value = []
        self.relation_get.return_value = None
        _config = {'min-cluster-size': None}
        self.config.side_effect = lambda key: _config.get(key)
        self.assertTrue(percona_utils.cluster_ready())

        # When VIP configured check is_clustered
        mock_is_sufficient_peers.return_value = True
        self.relation_ids.return_value = ['cluster:0']
        self.related_units.return_value = ['test/0', 'test/1']
        self.relation_get.return_value = 'UUID'
        _config = {'vip': '10.10.10.10', 'min-cluster-size': 3}
        self.config.side_effect = lambda key: _config.get(key)
        # HACluster not ready
        self.is_clustered.return_value = False
        self.assertFalse(percona_utils.cluster_ready())
        # HACluster ready
        self.is_clustered.return_value = True
        self.assertTrue(percona_utils.cluster_ready())

    @mock.patch.object(percona_utils, 'cluster_ready')
    def test_client_node_is_ready(self, mock_cluster_ready):
        # Paused
        self.is_unit_paused_set.return_value = True
        self.assertFalse(percona_utils.client_node_is_ready())

        # Cluster not ready
        mock_cluster_ready.return_value = False
        self.assertFalse(percona_utils.client_node_is_ready())

        # Not ready
        self.is_unit_paused_set.return_value = False
        mock_cluster_ready.return_value = True
        self.relation_ids.return_value = ['shared-db:0']
        self.leader_get.return_value = {}
        self.assertFalse(percona_utils.client_node_is_ready())

        # Ready
        self.is_unit_paused_set.return_value = False
        mock_cluster_ready.return_value = True
        self.relation_ids.return_value = ['shared-db:0']
        self.leader_get.return_value = {'shared-db:0_password': 'password'}
        self.assertTrue(percona_utils.client_node_is_ready())

    @mock.patch.object(percona_utils, 'cluster_ready')
    def test_leader_node_is_ready(self, mock_cluster_ready):
        # Paused
        self.is_unit_paused_set.return_value = True
        self.assertFalse(percona_utils.leader_node_is_ready())

        # Not leader
        self.is_unit_paused_set.return_value = False
        self.is_leader.return_value = False
        self.assertFalse(percona_utils.leader_node_is_ready())

        # Not cluster ready
        self.is_unit_paused_set.return_value = False
        self.is_leader.return_value = True
        mock_cluster_ready.return_value = False
        self.assertFalse(percona_utils.leader_node_is_ready())

        # Leader ready
        self.is_unit_paused_set.return_value = False
        self.is_leader.return_value = True
        mock_cluster_ready.return_value = True
        self.assertTrue(percona_utils.leader_node_is_ready())

    def test_cluster_wait(self):
        self.relation_ids.return_value = ['amqp:27']
        self.related_units.return_value = ['unit/1', 'unit/2', 'unit/3']
        # Default check peer relation
        _config = {'known-wait': 30}
        self.config.side_effect = lambda key: _config.get(key)
        percona_utils.cluster_wait()
        self.distributed_wait.assert_called_with(modulo=4, wait=30)

        # Use Min Cluster Size
        _config = {'min-cluster-size': 5, 'known-wait': 30}
        self.config.side_effect = lambda key: _config.get(key)
        percona_utils.cluster_wait()
        self.distributed_wait.assert_called_with(modulo=5, wait=30)

        # Override with modulo-nodes
        _config = {'min-cluster-size': 5, 'modulo-nodes': 10, 'known-wait': 60}
        self.config.side_effect = lambda key: _config.get(key)
        percona_utils.cluster_wait()
        self.distributed_wait.assert_called_with(modulo=10, wait=60)

        # Just modulo-nodes
        _config = {'modulo-nodes': 10, 'known-wait': 60}
        self.config.side_effect = lambda key: _config.get(key)
        percona_utils.cluster_wait()
        self.distributed_wait.assert_called_with(modulo=10, wait=60)


class TestResolveHostnameToIP(CharmTestCase):

    TO_PATCH = []

    def setUp(self):
        CharmTestCase.setUp(self, percona_utils,
                            self.TO_PATCH)

    @mock.patch.object(percona_utils, 'is_ipv6')
    @mock.patch.object(percona_utils, 'is_ip')
    @mock.patch.object(percona_utils, 'config', lambda *args: None)
    def test_resolve_hostname_to_ip_ips(self, mock_is_ip, mock_is_ipv6):
        ipv6_address = '2a01:348:2f4:0:dba7:dc58:659b:941f'
        ipv4_address = '10.10.10.2'
        self.assertEqual(percona_utils.resolve_hostname_to_ip(ipv6_address),
                         ipv6_address)
        self.assertTrue(mock_is_ip.called)
        self.assertFalse(mock_is_ipv6.called)
        self.assertEqual(percona_utils.resolve_hostname_to_ip(ipv4_address),
                         ipv4_address)
        self.assertTrue(mock_is_ip.called)
        self.assertFalse(mock_is_ipv6.called)

    @mock.patch.object(percona_utils, 'config', lambda *args: None)
    @mock.patch('dns.resolver.query')
    def test_resolve_hostname_to_ip_hostname_a(self,
                                               dns_query):
        mock_answer = mock.MagicMock()
        mock_answer.address = '10.10.10.20'
        dns_query.return_value = [mock_answer]
        self.assertEqual(percona_utils.resolve_hostname_to_ip('myhostname'),
                         '10.10.10.20')
        dns_query.assert_has_calls([
            mock.call('myhostname', 'A'),
        ])

    @mock.patch.object(percona_utils, 'is_ipv6')
    @mock.patch.object(percona_utils, 'is_ip')
    @mock.patch.object(percona_utils, 'config')
    @mock.patch('dns.resolver.query')
    def test_resolve_hostname_to_ip_hostname_aaaa(self, dns_query, mock_config,
                                                  mock_is_ip, mock_is_ipv6):

        def fake_config(key):
            return {'prefer-ipv6': True}.get(key)

        mock_config.side_effect = fake_config
        mock_answer = mock.MagicMock()
        mock_is_ipv6.return_value = False
        mock_answer.address = '2a01:348:2f4:0:dba7:dc58:659b:941f'
        dns_query.return_value = [mock_answer]
        self.assertEqual(percona_utils.resolve_hostname_to_ip('myhostname'),
                         '2a01:348:2f4:0:dba7:dc58:659b:941f')
        self.assertFalse(mock_is_ip.called)
        self.assertTrue(mock_is_ipv6.called)
        dns_query.assert_has_calls([
            mock.call('myhostname', 'AAAA'),
        ])

    @mock.patch.object(percona_utils, 'config', lambda *args: None)
    @mock.patch('dns.resolver.query')
    def test_resolve_hostname_to_ip_hostname_noanswer(self,
                                                      dns_query):
        dns_query.return_value = []
        self.assertEqual(percona_utils.resolve_hostname_to_ip('myhostname'),
                         None)
        dns_query.assert_has_calls([
            mock.call('myhostname', 'A'),
        ])


class TestUpdateBootstrapUUID(CharmTestCase):
    TO_PATCH = [
        'log',
        'leader_get',
        'get_wsrep_value',
        'relation_ids',
        'relation_set',
        'is_leader',
        'leader_set',
        'config',
        'leader_get',
    ]

    def setUp(self):
        CharmTestCase.setUp(self, percona_utils, self.TO_PATCH)
        self.log.side_effect = self.juju_log

    def juju_log(self, msg, level=None):
        print('juju-log %s: %s' % (level, msg))

    def test_no_bootstrap_uuid(self):
        self.leader_get.return_value = None
        self.assertRaises(percona_utils.LeaderNoBootstrapUUIDError,
                          percona_utils.update_bootstrap_uuid)

    def test_bootstrap_uuid_already_set(self):
        self.leader_get.return_value = '1234-abcd'

        def fake_wsrep(k):
            d = {'wsrep_ready': 'ON',
                 'wsrep_cluster_state_uuid': '1234-abcd'}
            return d[k]

        self.get_wsrep_value.side_effect = fake_wsrep
        self.relation_ids.return_value = ['cluster:2']
        self.is_leader.return_value = False
        percona_utils.update_bootstrap_uuid()
        self.relation_set.assert_called_with(relation_id='cluster:2',
                                             **{'bootstrap-uuid': '1234-abcd'})
        self.leader_set.assert_not_called()

        self.is_leader.return_value = True
        percona_utils.update_bootstrap_uuid()
        self.relation_set.assert_called_with(relation_id='cluster:2',
                                             **{'bootstrap-uuid': '1234-abcd'})
        self.leader_set.assert_called_with(**{'bootstrap-uuid': '1234-abcd'})

    @mock.patch.object(percona_utils, 'notify_bootstrapped')
    def test_bootstrap_uuid_could_not_be_retrieved(self, mock_notify):
        self.leader_get.return_value = '1234-abcd'

        def fake_wsrep(k):
            d = {'wsrep_ready': 'ON',
                 'wsrep_cluster_state_uuid': ''}
            return d[k]

        self.get_wsrep_value.side_effect = fake_wsrep
        self.assertFalse(percona_utils.update_bootstrap_uuid())
        mock_notify.assert_not_called()

    def test_bootstrap_uuid_diffent_uuids(self):
        self.leader_get.return_value = '1234-abcd'

        def fake_wsrep(k):
            d = {'wsrep_ready': 'ON',
                 'wsrep_cluster_state_uuid': '5678-dead-beef'}
            return d[k]

        self.get_wsrep_value.side_effect = fake_wsrep
        self.assertRaises(percona_utils.InconsistentUUIDError,
                          percona_utils.update_bootstrap_uuid)

    @mock.patch('charmhelpers.contrib.database.mysql.leader_set')
    @mock.patch('charmhelpers.contrib.database.mysql.is_leader')
    @mock.patch('charmhelpers.contrib.database.mysql.leader_get')
    def test_update_root_password(self, mock_leader_get, mock_is_leader,
                                  mock_leader_set):
        cur_password = 'openstack'
        new_password = 'ubuntu'
        leader_config = {'mysql.passwd': cur_password}
        mock_leader_get.side_effect = lambda k: leader_config[k]
        mock_is_leader.return_value = True

        self.config.side_effect = self.test_config.get
        self.assertFalse(percona_utils.update_root_password())

        self.test_config.set_previous('root-password', cur_password)
        self.test_config.set('root-password', new_password)
        percona_utils.update_root_password()

        mock_leader_set.assert_called_with(
            settings={'mysql.passwd': new_password})

    @mock.patch.object(percona_utils, 'leader_get')
    @mock.patch.object(percona_utils, 'get_db_helper')
    def test_update_root_password_None(self, mock_get_db_helper,
                                       mock_leader_get):
        # Test fix for 1744961
        my_mock = mock.Mock()
        mock_get_db_helper.return_value = my_mock
        self.config.side_effect = self.test_config.get
        leader_config = {'root-password': 'leaderpass'}
        mock_leader_get.side_effect = lambda k: leader_config[k]

        percona_utils.update_root_password()
        my_mock.set_mysql_root_password.assert_called_once_with('leaderpass')

    def test_is_leader_bootstrapped_once(self):
        leader_config = {'bootstrap-uuid': None, 'mysql.passwd': None,
                         'root-password': None, 'sst-password': None}
        self.leader_get.return_value = leader_config
        self.assertFalse(percona_utils.is_leader_bootstrapped())

        leader_config = {'bootstrap-uuid': 'UUID', 'mysql.passwd': None,
                         'root-password': None, 'sst-password': None}
        self.leader_get.return_value = leader_config
        self.assertFalse(percona_utils.is_leader_bootstrapped())

        leader_config = {'bootstrap-uuid': None, 'mysql.passwd': None,
                         'root-password': 'pass', 'sst-password': None}
        self.leader_get.return_value = leader_config
        self.assertFalse(percona_utils.is_leader_bootstrapped())

        leader_config = {'bootstrap-uuid': 'UUID', 'mysql.passwd': 'pass',
                         'root-password': 'pass', 'sst-password': 'pass',
                         'leader-ip': '10.10.10.10'}
        self.leader_get.return_value = leader_config
        self.assertTrue(percona_utils.is_leader_bootstrapped())
