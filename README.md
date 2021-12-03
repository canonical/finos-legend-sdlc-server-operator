[![FINOS - Incubating](https://cdn.jsdelivr.net/gh/finos/contrib-toolbox@master/images/badge-incubating.svg)](https://finosfoundation.atlassian.net/wiki/display/FINOS/Incubating)

# FINOS Legend SDLC Operator

## Description

The Legend Operators package the core [FINOS Legend](https://legend.finos.org)
components for quick and easy deployment of a Legend stack.

This repository contains a [Juju](https://juju.is/) Charm for
deploying the SDLC, the model-centric metadata server for Legend.

The full Legend solution can be installed with the dedicated
[Legend bundle](https://charmhub.io/finos-legend-bundle).


## Usage

The SDLC Operator can be deployed by running:

```sh
$ juju deploy finos-legend-sdlc-k8s --channel=edge
```


## Relations

The standalone SDLC will initially be blocked, and will require being later
related to the [Legend Database Operator](https://github.com/canonical/finos-legend-db-operator),
as well as the [Legend GitLab Integrator](https://github.com/canonical/finos-legend-gitlab-integrator).

```sh
$ juju deploy finos-legend-db-k8s finos-legend-gitlab-integrator-k8s
$ juju relate finos-legend-sdlc-k8s finos-legend-db-k8s
$ juju relate finos-legend-sdlc-k8s finos-legend-gitlab-integrator-k8s
# If relating to Legend Studio:
$ juju relate finos-legend-sdlc-k8s finos-legend-studio-k8s
```

## OCI Images

This charm by default uses the latest version of the
[finos/legend-sdlc-server](https://hub.docker.com/r/finos/legend-sdlc-server) image.

## Contributing

Visit Legend [Contribution Guide](https://github.com/finos/legend/blob/master/CONTRIBUTING.md) to learn how to contribute to Legend.

## License

Copyright (c) 2021-present, Canonical

Distributed under the [Apache License, Version 2.0](http://www.apache.org/licenses/LICENSE-2.0).

SPDX-License-Identifier: [Apache-2.0](https://spdx.org/licenses/Apache-2.0)
