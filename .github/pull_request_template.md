# What this changes

<!-- What the change does and why. Link the issue it closes. -->

## Validation

<!-- Which of these you ran and anything that failed. -->

- [ ] `python -m pytest`
- [ ] `python -m pytest tests/test_browser_e2e.py`, for a Web Dashboard change
- [ ] `mkdocs build --strict`, for a documentation change
- [ ] `docker build .`, for a container or packaging change
- [ ] Exercised against a real Instagram account, for a detection or session change

<!-- A monitoring or session change is not verified by the offline suite alone, which never contacts
     Instagram. Say what you ran it against, without usernames or credentials. -->

## Documentation and release notes

- [ ] User-facing behavior is documented under `docs/`
- [ ] `RELEASE_NOTES.md` carries an entry or the change is not user facing

## Anything a reviewer should know

<!-- Trade-offs, follow-up work or parts you are unsure about. -->

<!-- Never include session cookies, Instagram or SMTP passwords, webhook URLs, ntfy tokens or the
     usernames you monitor in a pull request. -->
