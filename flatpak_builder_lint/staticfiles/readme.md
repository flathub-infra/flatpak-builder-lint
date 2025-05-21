### Summary files

`flathub-stable.summary` and `flathub-beta.summary` are
[Flatpak summary](https://github.com/flatpak/flatpak/blob/66b038e14809bc973d46e8078a070dc32e894903/doc/flatpak-summaries.txt)
files for Flathub stable and beta repositories respectively. The source
is at `http://dl.flathub.org/repo/summary` and at
`http://dl.flathub.org/beta-repo/summary` respectively. These files are
used as a fallback by `flatpak-builder-lint` when downloading over the
network fails.

The code to parse and read them is available in
`flatpak_builder_lint/domainutils.py`. They can also be viewed by doing:

```sh
ostree init --repo=repo
cp flathub-stable.summary repo/summary
ostree --repo=repo summary -v
```

These are available at `http://dl.flathub.org/repo/summary`
and at `http://dl.flathub.org/beta-repo/summary` respectively.

These files are updated automatically in CI.
