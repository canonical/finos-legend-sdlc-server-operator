#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
import pathlib

import pytest
import requests
import tenacity
import yaml
from pytest_operator import plugin as pytest_plugin

logger = logging.getLogger(__name__)

LEGEND_HOST = "finos-legend"
GITLAB_CLIENT_ID = "fake-client"
GITLAB_CLIENT_SECRET = "fake-secret"

METADATA = yaml.safe_load(pathlib.Path("./metadata.yaml").read_text())
APP_NAME = METADATA["name"]

MONGODB_APP_NAME = "mongodb-k8s"
ENGINE_APP_NAME = "finos-legend-engine-k8s"
SDLC_APP_NAME = "finos-legend-sdlc-k8s"
STUDIO_APP_NAME = "finos-legend-studio-k8s"
LEGEND_DB_APP_NAME = "finos-legend-db-k8s"
GITLAB_INTEGRATOR_APP_NAME = "finos-legend-gitlab-integrator-k8s"
NGINX_INGRESS_CHARM = "nginx-ingress-integrator"

# TODO: Add STUDIO_APP_NAME to the list below once the following issue has been resolved:
# https://github.com/finos/legend-studio/issues/1028
LEGEND_APPS = [ENGINE_APP_NAME, SDLC_APP_NAME]
LEGEND_APPS_CONFIG = [ENGINE_APP_NAME, SDLC_APP_NAME, STUDIO_APP_NAME]

APP_LIST = [
    MONGODB_APP_NAME,
    LEGEND_DB_APP_NAME,
    SDLC_APP_NAME,
    ENGINE_APP_NAME,
    STUDIO_APP_NAME,
    GITLAB_INTEGRATOR_APP_NAME,
]
OTHER_APPS = [
    MONGODB_APP_NAME,
    LEGEND_DB_APP_NAME,
    ENGINE_APP_NAME,
    STUDIO_APP_NAME,
    GITLAB_INTEGRATOR_APP_NAME,
]

APP_PORTS = {
    ENGINE_APP_NAME: 6060,
    SDLC_APP_NAME: 7070,
    STUDIO_APP_NAME: 8080,
}
APP_ROUTES = {
    ENGINE_APP_NAME: "/engine",
    SDLC_APP_NAME: "/api",
    STUDIO_APP_NAME: "/studio",
}


@tenacity.retry(
    retry=tenacity.retry_if_result(lambda x: x is False),
    stop=tenacity.stop_after_attempt(10),
    wait=tenacity.wait_exponential(multiplier=1, min=5, max=30),
)
def check_legend_connection(app_name, url, headers=None):
    """Tests the connection to the given Legend URL.
    When connecting to the FINOS Legend Applications, it will redirect to gitlab for
    authentication, which will not be a 20X status code. We will receive 302 Found
    instead.
    Returns True if the response status code is 302, False in any other case.
    """
    logger.info("Trying to access %s...", app_name)
    try:
        response = requests.get(url, headers=headers, allow_redirects=False, timeout=10)
        return response.status_code == 302
    except Exception as ex:
        logger.info(ex)
    return False


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: pytest_plugin.OpsTest):
    """Build the charm-under-test and deploy it together with related charms."""
    # build and deploy charm from local source folder
    charm = await ops_test.build_charm(".")
    resources = {"sdlc-image": METADATA["resources"]["sdlc-image"]["upstream-source"]}
    await ops_test.model.deploy(charm, resources=resources, application_name=APP_NAME)

    for name in OTHER_APPS:
        await ops_test.model.deploy(name, channel="edge")

    await ops_test.model.add_relation(LEGEND_DB_APP_NAME, MONGODB_APP_NAME)
    for app in LEGEND_APPS_CONFIG:
        await ops_test.model.add_relation(LEGEND_DB_APP_NAME, app)
        await ops_test.model.add_relation(GITLAB_INTEGRATOR_APP_NAME, app)

    for app in LEGEND_APPS:
        await ops_test.model.add_relation(STUDIO_APP_NAME, app)


@pytest.mark.abort_on_fail
async def test_config_gitlab(ops_test: pytest_plugin.OpsTest):
    """Set the gitlab.com's application secret ID and name.
    After setting the application secret ID and name, the charms should become active.
    """
    # We need valid information here. These should be passed in through the env variables.
    gitlab_integrator = ops_test.model.applications[GITLAB_INTEGRATOR_APP_NAME]
    await gitlab_integrator.set_config(
        {"gitlab-client-id": GITLAB_CLIENT_ID, "gitlab-client-secret": GITLAB_CLIENT_SECRET}
    )

    # Wait for all the charms to become Active.
    await ops_test.model.wait_for_idle(apps=APP_LIST, status="active", timeout=2000)

    # effectively disable the update status from firing
    await ops_test.model.set_config({"update-status-hook-interval": "60m"})


@pytest.mark.abort_on_fail
async def test_applications_are_up(ops_test: pytest_plugin.OpsTest):
    """Test the direct FINOS Legend connection.
    The FINOS Legend application services should be accessible through their IP, ports,
    and routes.
    """
    status = await ops_test.model.get_status()

    for app_name in LEGEND_APPS:
        unit_name = "%s/0" % app_name
        address = status["applications"][app_name]["units"][unit_name]["address"]

        url = "http://%s:%s%s" % (address, APP_PORTS[app_name], APP_ROUTES[app_name])
        can_connect = check_legend_connection(app_name, url)

        assert can_connect, "Could not reach %s through its IP." % app_name
        logger.info("Successfully reached %s through its IP.", app_name)


@pytest.mark.abort_on_fail
async def test_nginx_ingress_integration(ops_test: pytest_plugin.OpsTest):
    """Test the FINOS Legend connection through NGINX Ingress.
    The Legend applications have been configured with their names by default,
    and they should be accessible through it due to the nginx-ingress-integrator charm.
    """
    # We should now be able to connect to FINOS Legend through its hostname (the name of
    # the specific app). In this test scenario, we don't have a resolver for it.
    # One could configure the /etc/hosts file to have the line:
    # 127.0.0.1 legend-host
    # Having the line above would resolve the hostname. For the current testing purposes, we
    # can simply connect to 127.0.0.1 and having the hostname as a header. This is the
    # equivalent of:
    # curl --header 'Host: legend-host' http://127.0.0.1

    await ops_test.model.deploy(NGINX_INGRESS_CHARM, channel="edge", trust=True)

    for name in LEGEND_APPS_CONFIG:
        await ops_test.model.add_relation(NGINX_INGRESS_CHARM, name)

    for app_name in LEGEND_APPS_CONFIG:
        url = "http://127.0.0.1%s" % APP_ROUTES[app_name]
        headers = {"Host": app_name}
        can_connect = check_legend_connection(app_name, url, headers)

        assert can_connect, "Could not reach %s through its service-hostname." % app_name

        logger.info("Successfully reached %s through its service-hostname.", app_name)

    # configure and check connection to external host
    sdlc = ops_test.model.applications[SDLC_APP_NAME]
    await sdlc.set_config({"external-hostname": LEGEND_HOST})

    url = "http://127.0.0.1%s" % APP_ROUTES[SDLC_APP_NAME]
    headers = {"Host": LEGEND_HOST}
    can_connect = check_legend_connection(SDLC_APP_NAME, url, headers)

    assert can_connect, "Could not reach %s through its external-hostname." % SDLC_APP_NAME

    logger.info("Successfully reached %s through its external-hostname.", SDLC_APP_NAME)