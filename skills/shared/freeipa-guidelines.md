# FreeIPA Contribution Guidelines — Agent Review Reference

This file is a condensed reference of FreeIPA's upstream contribution
standards, sourced from the official documentation:

- [Contribute/Code](https://www.freeipa.org/page/Contribute/Code)
- [Python Coding Style](https://www.freeipa.org/page/Python_Coding_Style)
- [Coding Best Practices](https://www.freeipa.org/page/Coding_Best_Practices)
- [Coding Style](https://www.freeipa.org/page/Coding_Style)

It is used by the commit and PR skills to validate code changes
against FreeIPA conventions.

---

## MUST — Violations that should block or warn loudly

### No star imports

```python
# WRONG
from ipalib.plugins.baseldap import *

# RIGHT
from ipalib.plugins.baseldap import LDAPCreate
# or
from ipalib.plugins import baseldap
```

Star imports make it harder to trace where names come from and can
shadow variables.

### i18n strings: use named format specifiers

Any translatable string (`_()`) with two or more format substitutions
MUST use **named** specifiers so translators can reorder words.

```python
# WRONG — positional
_('item %s has %s value') % (name, value)

# RIGHT — named
_('item %(name)s has %(value)s value') % {'name': name, 'value': value}
```

For C code, use indexed specifiers (`%1$s`, `%2$s`) instead of
positional (`%s`).

### Unused variables must start with `_`

The pylint config enforces `dummy-variables-rgx=(_.+|unused)`.  Any
variable used only to discard a value (loop iteration, tuple
unpacking) must be prefixed with an underscore.

```python
# WRONG
name, weight, age = human['John']

# RIGHT
name, _weight, age = human['John']
```

### Forbidden cross-package imports

FreeIPA enforces import boundaries between packages (via `pylintrc`
`[IPA]` `forbidden-imports`).  The key rules:

- `ipaclient/` must NOT import from `ipaserver`
- `ipalib/` must NOT import from `ipaserver`
- `ipaplatform/` must NOT import from `ipaclient`, `ipalib`,
  or `ipaserver`
- `ipapython/` must NOT import from `ipaclient`, `ipalib`,
  or `ipaserver`
- `ipatests/test_integration` must NOT import from `ipaserver`

### Commit message format

Every commit must follow the `.git-commit-template`:

```
component: Subject

Explanation of the fix/feature and the implementation approach.

Fixes: https://codeberg.org/freeipa/freeipa/issues/XXXX
Signed-off-by: Full Name <email@example.com>
```

- **`component: Subject`** — single-line summary, imperative mood
- **Explanation** — must describe *what* and *how*, can span multiple
  lines
- **`Fixes:`** — commit resolves the issue
- **`Related:`** — commit is related but does not resolve the issue
- Do NOT confuse `Fixes:` with `Related:`
- Issue URLs must use **Codeberg**
  (`https://codeberg.org/freeipa/freeipa/issues/XXXX`),
  NOT the old Pagure URLs

### Line length

- MUST NOT exceed **120 characters**
- HIGHLY RECOMMENDED to stay within **80 characters**
  (pycodestyle enforces `max-line-length = 80`)

### Indentation

- 4 spaces, no tabs — for all code (Python and C)

### Naming

- Use **lowercase underscore-separated** names for variables and
  functions (e.g. `monitor_task_init`)
- Never use Hungarian notation

---

## SHOULD — Warn but don't block

### Decorator-based plugin registration

New plugins must use the `@register()` decorator pattern:

```python
# WRONG (obsolete)
from ipalib import api
class myobj_mod(LDAPUpdate): ...
api.register(myobj_mod)

# RIGHT (current)
from ipalib.plugable import Registry
register = Registry()

@register()
class myobj_mod(LDAPUpdate): ...
```

The decorator must be named `register`.

### Split long translatable strings

Long translatable strings (especially `__doc__`) should be split by
paragraph so only affected parts need re-translation:

```python
__doc__ = _("""
Foo Plugin
""") + _("""
This plugin allows management of enterprise foos and bars.
""") + _("""
Here is a second paragraph.
""")
```

Only split when the string is being changed — splitting unchanged
strings forces unnecessary re-translation.

### LDAPEntry dict-like API

Do NOT unpack LDAPEntry as a tuple:

```python
# WRONG (obsolete)
dn, attrs = entry
values = attrs[attrname]

# RIGHT (current)
dn = entry.dn
values = entry[attrname]
```

### Use the admintool framework

Installation and management scripts should use the admintool framework
for argument parsing, logging, error handling, and interactive
prompting — not roll their own.

### Meaningful comments

Comments should explain **why**, not **what**.  The code tells us how;
the comment tells us why.

### Single logical change per commit

Keep commits limited to one logical change.  Multiple commits in the
same PR are fine — they help demonstrate the logic and isolate changes.

### Tests for every ticket

For each ticket, a corresponding test must be written.  If the PR-CI
does not cover the fix, the PR description must list:
- Which tests in `ipatests/` validate the fix
- What manual testing was performed

### Associated Codeberg ticket

All PRs need an associated Codeberg ticket unless the change is
trivial.

---

## Out of Scope — Handled by `make fastcheck`

The following checks are enforced by FreeIPA's existing CI tooling
(`make fastlint`, `make fasttest`, `make fastcheck`).  The agent
should NOT try to replicate them but should remind the contributor
to run `make fastcheck` before submitting:

- **pycodestyle** — runs on diff; configured in `tox.ini`
  (`ignore = E203, E402, E231, W503, E731, E741`)
- **pylint** — runs with `pylintrc` and `pylint_plugins.py`
  (including the `IPAChecker` for forbidden imports)
- **acilint** — ACI validation
- **apilint** — API schema validation
- **yamllint** — YAML file validation

---

## pycodestyle Exceptions (reference)

These pycodestyle errors are intentionally ignored project-wide
(from `tox.ini`):

| Code | Description | Reason |
|------|-------------|--------|
| E203 | whitespace before `:` | not PEP-8 |
| E231 | missing whitespace after `,` | used by black |
| E402 | module level import not at top | |
| W503 | line break before binary operator | not PEP-8 |
| E731 | do not assign a lambda expression | |
| E741 | ambiguous variable name `l` | |
