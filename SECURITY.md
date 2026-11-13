# Security

漫构 is a **local-only** application. It binds to `127.0.0.1:8787` by default,
has no user authentication, and is not designed to be exposed to the public
internet.

## Please do not

- change `HOST` to `0.0.0.0` on an untrusted network;
- put API keys in tracked files (use the in-app settings, stored in
  `data/config.json`, which is gitignored);
- commit `.tools/`, model weights, or rendered private projects.

## Reporting

If you find a security issue, please open a private security advisory on the
GitHub repository rather than a public issue. Include reproduction steps and
the version from `VERSION`.
