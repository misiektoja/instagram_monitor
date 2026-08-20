# Third-party notices

instagram_monitor original code is licensed under GPL-3.0-or-later. See [LICENSE](LICENSE).

The distributed package contains no vendored third-party source. It declares the dependencies below, which are installed from PyPI under their own licenses and remain the property of their authors. The Web Dashboard template ships no bundled or CDN-hosted JavaScript or CSS.

## Runtime dependencies

| Component | Required version | License | Use |
| --- | --- | --- | --- |
| [instaloader](https://github.com/instaloader/instaloader) | >=4.15.1 | MIT | Instagram session handling, profile, post and story retrieval |
| [requests](https://github.com/psf/requests) | >=2.0 | Apache-2.0 | HTTP for notifications, media downloads and proxy IP lookups |
| [curl_cffi](https://github.com/lexiforest/curl_cffi) | >=0.7 | MIT | Browser TLS impersonation for the alternative HTTP backend |
| [python-dateutil](https://github.com/dateutil/dateutil) | >=2.8 | Apache-2.0 or BSD-3-Clause | Timestamp parsing and relative date arithmetic |
| [pytz](https://github.com/stub42/pytz) | >=2020.1 | MIT | Timezone conversion for displayed and logged times |
| [tzlocal](https://github.com/regebro/tzlocal) | >=4.0 | MIT | Local timezone detection |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | >=0.19 | BSD-3-Clause | Reading secrets from `.env` |
| [tqdm](https://github.com/tqdm/tqdm) | >=4.0 | MPL-2.0 and MIT | Progress bars for follower and following downloads |
| [Flask](https://github.com/pallets/flask) | >=2.0 | BSD-3-Clause | Web Dashboard HTTP server and API |
| [Jinja2](https://github.com/pallets/jinja) | >=3.0 | BSD-3-Clause | Web Dashboard and HTML email templating |
| [Rich](https://github.com/Textualize/rich) | >=12.0 | MIT | Terminal dashboard rendering |
| [colorama](https://github.com/tartley/colorama) | >=0.4.6, Windows only | BSD-3-Clause | ANSI color support on Windows terminals |
| [pycookiecheat](https://github.com/n8henrie/pycookiecheat) | >=0.8, `browser` extra | MIT | Importing Chrome, Brave and Chromium sessions on macOS and Linux |

## Build, test and documentation dependencies

These are not installed with the package and are not redistributed with it.

| Component | License | Use |
| --- | --- | --- |
| [pytest](https://github.com/pytest-dev/pytest) | MIT | Test suite |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | Validating workflows and issue templates in the test suite |
| [Playwright](https://github.com/microsoft/playwright-python) | Apache-2.0 | Browser end-to-end tests for the Web Dashboard |
| [build](https://github.com/pypa/build), [setuptools](https://github.com/pypa/setuptools), [wheel](https://github.com/pypa/wheel) | MIT | Package build |
| [MkDocs Material](https://github.com/squidfunk/mkdocs-material) | MIT | Documentation site |

## Container image

The published Docker image is built on the official [`python:3.14-slim-bookworm`](https://hub.docker.com/_/python) image and inherits the licenses of Debian and the Python distribution it carries.

## Derived code

The Instagram GraphQL query handling in `instagram_monitor.py` ports instaloader pull requests [#2696](https://github.com/instaloader/instaloader/pull/2696) and [#2706](https://github.com/instaloader/instaloader/pull/2706), which migrate profile and post metadata retrieval to current `doc_id` endpoints after Instagram removed the previous ones. instaloader is MIT licensed, which permits use in this GPL-3.0-or-later project. Both patches are applied at runtime and deactivate themselves once instaloader ships the equivalent fix upstream. Attribution and the reason for each patch are recorded at the call sites.

## Reporting a licensing problem

If a component is listed incorrectly or a notice is missing, open an issue. This manually maintained notice does not replace the license texts distributed by the dependency authors.
