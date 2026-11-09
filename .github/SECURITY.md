# security policy

## reporting a vulnerability

please do not open a public issue for security problems.

use GitHub's private vulnerability reporting for this repository if it is available. otherwise, contact the maintainer through the support link on the website and include:

- what the issue is
- how it can be reproduced
- what an attacker could do with it
- any suggested fix

please give the maintainer time to respond before sharing details publicly.

## secrets

never commit `.env`, bot tokens, webhook URLs, or database files. they are ignored by git for a reason.
