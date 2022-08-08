# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module testing the Legend SDLC Operator."""

import inspect
import json
import os
import pathlib

from charms.finos_legend_libs.v0 import legend_operator_testing
from ops import testing as ops_testing

import charm


class LegendSdlcTestWrapper(charm.LegendSDLCServerCharm):
    @classmethod
    def _get_relations_test_data(cls):
        return {
            cls._get_legend_db_relation_name(): {
                "legend-db-connection": json.dumps(
                    {
                        "username": "test_db_user",
                        "password": "test_db_pass",
                        "database": "test_db_name",
                        "uri": "test_db_uri",
                    }
                )
            },
            cls._get_legend_gitlab_relation_name(): {
                "legend-gitlab-connection": json.dumps(
                    {
                        "gitlab_host": "gitlab_test_host",
                        "gitlab_port": 7667,
                        "gitlab_scheme": "https",
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "openid_discovery_url": "test_discovery_url",
                        "gitlab_host_cert_b64": "test_gitlab_cert",
                    }
                )
            },
        }

    def _get_service_configs_clone(self, relation_data):
        return {}


class LegendSdlcTestCase(legend_operator_testing.TestBaseFinosCoreServiceLegendCharm):

    __metadata_yaml = None
    __config_yaml = None

    @classmethod
    def _charm_file_content(cls, filename):
        cls_filename = inspect.getfile(cls)
        charm_dir = pathlib.Path(cls_filename).parents[2]
        with open(os.path.join(charm_dir, filename), "r") as f:
            return f.read()

    @classmethod
    def _metadata_yaml(cls):
        if cls.__metadata_yaml is None:
            cls.__metadata_yaml = cls._charm_file_content("metadata.yaml")
        return cls.__metadata_yaml

    @classmethod
    def _config_yaml(cls):
        if cls.__config_yaml is None:
            cls.__config_yaml = cls._charm_file_content("config.yaml")
        return cls.__config_yaml

    @classmethod
    def _set_up_harness(cls):
        # According to the Harness documentation, if it doesn't get any meta or config arguments,
        # it will look for the metadata.yaml and config.yaml files in the parent folder.
        # However, this file has been moved from tests to tests/unit which means that those files
        # are one level above than expected. We have to manually pass those arguments ourselves.
        harness = ops_testing.Harness(
            LegendSdlcTestWrapper, meta=cls._metadata_yaml(), config=cls._config_yaml()
        )
        return harness

    def test_get_core_legend_service_configs(self):
        self._test_get_core_legend_service_configs()

    def test_relations_waiting(self):
        self._test_relations_waiting()

    def test_studio_relation_joined(self):
        self.harness.set_leader(True)
        self.harness.begin_with_initial_hooks()

        relator_name = "finos-legend-studio-k8s"
        rel_id = self.harness.add_relation(charm.LEGEND_STUDIO_RELATION_NAME, relator_name)
        relator_unit = "%s/0" % relator_name
        self.harness.add_relation_unit(rel_id, relator_unit)
        self.harness.update_relation_data(rel_id, relator_unit, {})

        rel = self.harness.charm.framework.model.get_relation(
            charm.LEGEND_STUDIO_RELATION_NAME, rel_id
        )
        self.assertEqual(
            rel.data[self.harness.charm.app],
            {"legend-sdlc-url": self.harness.charm._get_sdlc_service_url()},
        )

    def test_get_legend_gitlab_redirect_uris(self):
        self.harness.begin()
        actual_uris = self.harness.charm._get_legend_gitlab_redirect_uris()

        base_url = "http://%s%s" % (
            self.harness.charm.app.name,
            charm.SDLC_INGRESS_ROUTE,
        )
        expected_url_api = "%s/auth/callback" % base_url
        expected_url_pac4j = "%s/pac4j/login/callback" % base_url
        self.assertEqual([expected_url_api, expected_url_pac4j], actual_uris)

        # Test with enable-tls set.
        self.harness.update_config({"enable-tls": True})
        actual_uris = self.harness.charm._get_legend_gitlab_redirect_uris()

        base_url = "https://%s%s" % (
            self.harness.charm.app.name,
            charm.SDLC_INGRESS_ROUTE,
        )
        expected_url_api = "%s/auth/callback" % base_url
        expected_url_pac4j = "%s/pac4j/login/callback" % base_url
        self.assertEqual([expected_url_api, expected_url_pac4j], actual_uris)

    def test_config_changed_update_gitlab_relation(self):
        self._test_update_config_gitlab_relation()

    def test_config_changed_update_studio_relation(self):
        self.harness.set_leader(True)
        self.harness.begin_with_initial_hooks()

        # Setup the initial relation with Legend Studio.
        rel_id = self._add_relation(charm.LEGEND_STUDIO_RELATION_NAME, {})

        # Update the config, and expect the relation data to be updated.
        hostname = "foo.lish"
        self.harness.update_config({"external-hostname": hostname, "enable-tls": True})

        rel = self.harness.charm.framework.model.get_relation(
            charm.LEGEND_STUDIO_RELATION_NAME, rel_id
        )
        expected_url = "https://%s%s" % (hostname, charm.APPLICATION_ROOT_PATH)
        self.assertEqual(
            rel.data[self.harness.charm.app],
            {"legend-sdlc-url": expected_url},
        )

    def test_upgrade_charm(self):
        self._test_upgrade_charm()

    def test_get_sdlc_service_url(self):
        self.harness.set_leader(True)
        self.harness.begin_with_initial_hooks()

        # Test without external-hostname config.
        actual_url = self.harness.charm._get_sdlc_service_url()

        expected_url = "http://%s%s" % (self.harness.charm.app.name, charm.APPLICATION_ROOT_PATH)
        self.assertEqual(expected_url, actual_url)

        # Test with external-hostname config.
        hostname = "foo.lish"
        self.harness.update_config({"external-hostname": hostname})
        actual_url = self.harness.charm._get_sdlc_service_url()

        expected_url = "http://%s%s" % (hostname, charm.APPLICATION_ROOT_PATH)
        self.assertEqual(expected_url, actual_url)

        # Test with enable-tls set.
        self.harness.update_config({"enable-tls": True})
        actual_url = self.harness.charm._get_sdlc_service_url()

        expected_url = "https://%s%s" % (hostname, charm.APPLICATION_ROOT_PATH)
        self.assertEqual(expected_url, actual_url)
