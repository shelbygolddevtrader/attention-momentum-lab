# Professional Strategy Olympics Execution Runtime V010

Status: `DESIGN_ONLY_V010_EXECUTION_RUNTIME_VALID_NO_RUNTIME_OR_EXECUTION_CAPABILITY`

V010 resolves one contradiction and nothing else. The historical V005/V006
command starts `.venv/bin/python` from the detached source root, while V005 and
V007 require that root to contain no ignored or untracked objects. A normal
`.venv` is ignored, absent from the authorized Git tree, usually contains
interpreter symlinks, and cannot satisfy the closed-world source inventory.
V010 does not relax that boundary.

## Selected architecture

Exactly one model is valid: a package-bound standalone CPython runtime on a
dedicated, external, read-only local APFS volume. It is neither a developer
virtual environment nor a subtree of the source checkout. Runtime creation and
approval remain future, separately reviewed work.

The detached source remains tracked-source only. Ignored files and directories
are filesystem objects and are prohibited. A complete descriptor-relative
filesystem enumeration—not `git status` alone—must detect them. The only source
inventory exclusion remains
`config/professional_strategy_olympics_operator_implementation_v001.json`, as
already frozen by V007.

For the invocation, the exact detached source is mounted on its own read-only
local APFS volume. Disk images, network or removable filesystems, writable
mounts, and mutation observations fail closed. This prevents the entry script
or an imported source file from changing after validation but before Python
opens it; it adds no ignored object or inventory exclusion.

## Command supersession

The historical V005 command and identity remain immutable history. A
V010-capable package must bind the V010 command and may not select or fall back
to the historical command.

The exact successor template is:

```text
{execution_runtime_root}/bin/python3 -s -S -B -P scripts/run_professional_strategy_olympics_v005.py --authorization {authorization_path} --source-root {detached_source_root} --consumption-root {consumption_root} --artifact-root {artifact_root} --clock-attestation {execution_clock_attestation_path} --runtime-descriptor {execution_runtime_descriptor_path}
```

Its identity domain is `aml.olympics.v010.command`. The executable is an
absolute descriptor-bound path. Shells, `PATH`, shebangs, current-directory
resolution, optional arguments, launchers, and fallback executables are
prohibited.

The authorization path must derive the exact V005/V007 package root. The clock
bootstrap and V010 runtime-descriptor arguments are then derived from that same
root and authorization identity; callers cannot choose alternate absolute
paths that happen to contain valid bytes.

The successor command identity is
`f9d7923bf58a6055e2276d4bdbe4c474f5c0ab7d7d6752dabc7648461fb04c75`.

## Runtime descriptor and inventory

The descriptor binds the authorization, V004–V010 lineage, successor command,
operator implementation, cycle-free V010 package binding, absolute runtime
root, interpreter, authorization-specific inventory, authorization-independent
runtime-content identity, dependency lock, package environment, platform boundary, Python
implementation/version/ABI, architecture, APFS volume, ownership, and mutation
policy. Unknown or missing fields reject.

The inventory covers every runtime directory and regular file, every Mach-O
dependency edge, the complete selected-architecture dyld shared-cache set, and
every macOS platform image required to start Python, import the operator, and
run the frozen computation. This is important on current macOS releases,
where install names such as `/usr/lib/libSystem.B.dylib` resolve into a shared
cache and are not necessarily readable as ordinary files.

Regular-file entries bind path, type, mode, length, SHA-256, owner, group,
link count, executable state, Mach-O status, dependency count, embedded code
signature digest when present, and the absence of ACLs, xattrs, and file flags.
Directory entries bind path, mode, owner, group, and the same metadata-absence
claims. The runtime root's filesystem, volume UUID, owner, group, mode, ACL,
xattrs, and file flags are also inside the authorization-independent content
identity; its ACL, xattrs, and flags must be absent. All raw cache-container
files are byte-bound; each resolved platform
image binds its logical install name, extracted bytes, UUID, cache-set identity,
and platform-boundary identity.

Runtime files are `0444` or `0555`; directories and the root are `0555`.
Regular files must have one link. Symlinks, mount crossings, devices, sockets,
FIFOs, aliases, duplicate paths, extra files, missing files, ACLs, mutable
xattrs, and unsupported modes reject. The entire volume is read-only for the
invocation.

## Interpreter and import closure

`bin/python3` must be a copied, regular executable, not a symlink or base
interpreter reference. V010 deliberately does not authorize a normal virtual
environment. `pyvenv.cfg`, activation files, package installation, editable
installs, and external package resolution are prohibited.

Python starts with `-s -S -B -P`. The monolithic `-I` flag is prohibited
because it would ignore the required `PYTHONHASHSEED=0`; the explicit flags
retain user-site, `site`, bytecode, and unsafe-path protections while allowing
the closed-world seed to take effect. Only inventory-bound runtime import
roots and the V007-identity-covered detached `src` root may be introduced after
pre-execution validation. `.pth`, `.egg-link`, `.pyc`, zip imports,
`sitecustomize`, and `usercustomize` are prohibited. Namespace packages cannot
extend paths beyond the frozen roots.

The entry point may use only the already bound standard library for its
bootstrap. Before any `aml` or third-party import, it replaces `sys.path` with
exactly the detached `src` root followed by the absolute inventory-declared
runtime import roots in inventory order. A missing, extra, reordered, or aliased
entry rejects. This is how `-P` and the absence of `PYTHONPATH` remain compatible
with importing the tracked operator code; no future implementation may invent a
different import bootstrap.

The package chooses one exact CPython version of at least 3.11.0, where `-P`
is supported. Its ABI text must exactly match the major/minor version and
architecture, and the same version must be present in the V005 environment
manifest; the operator cannot select another installed interpreter.

Every Mach-O file declares its exact dependency-edge count, and every load edge
must resolve to one runtime-inventory file or one logical image in the bound
dyld cache set. Absolute, `@executable_path`, and `@loader_path` install names
are allowed only when their exact resolved targets match that graph. `@rpath`
is prohibited because V010 does not freeze dyld's runpath-stack algorithm; a
future implementation may not assert an arbitrary `@rpath` resolution. If the
cache containers, extracted image bytes, dyld graph, or
platform closure cannot be read and reproduced, the result is indeterminate.
V010 does not claim kernel, secure-boot, or physical-disk authenticity.

The dependency-lock identity is not an opaque package-author assertion. It is
recomputed from the Python implementation, version, ABI, architecture,
interpreter file identity, ordered import roots, and every ordered runtime-file
identity. The package-environment identity binds that lock together with the
complete runtime-content and macOS platform identities.

## Source/runtime separation

The source and runtime roots must not be equal or nested. Their canonical paths,
devices, mounts, APFS volume UUIDs, and root inodes must differ. Cross-root hard
links, symlink aliases, bind mounts, and shared mutable files are prohibited.
Copy-on-write block sharing is not an alias when the inodes and volumes differ
and the runtime volume remains read-only; raw-byte identities still apply.

## Invocation mechanics

A future V010-capable launch supervisor will perform the frozen non-mutating
preflight and direct `execve`. V010 defines this interface but implements no
launcher. The supervisor is bound by the operator implementation identity and
receives no authorization or lifecycle authority.

The offline authorization-package author creates the descriptor and inventory
after the authorization identity is known; that act grants no approval. The
future supervisor distrusts those assertions and recomputes them from open
descriptors. The records have no wall-clock freshness window: they are valid
only for their one bound authorization/operator/package lineage and are
invalidated by any source, runtime, platform, package, or point-of-use change.

The launch uses the absolute interpreter path, no shell and no `PATH` lookup.
File descriptors above 2 are closed; standard streams are exact `/dev/null`
descriptors; umask is `0077`; signals and mask are reset; core dumps are
disabled; and a new session/process group is used. The working directory remains
the detached source root. The preflight binds that command argument and working
directory to the exact source root in the validated source observation; a valid
observation for one root cannot be paired with a command naming another.

The source and runtime are validated before launch and again at point of
execution while matching root descriptors are held. Both read-only APFS mounts,
their root devices, inodes, volumes, ownership, inventories, metadata, dyld
cache, Mach-O closure, and import closure must be unchanged. After start, the
operator must revalidate the source and runtime before imports beyond the
standard library and before the V008 invocation claim. Uncertainty is
indeterminate and cannot execute.

## Closed environment

The complete environment is:

```text
LANG=C
LC_ALL=C
PYTHONHASHSEED=0
PYTHONDONTWRITEBYTECODE=1
PYTHONNOUSERSITE=1
PYTHONSAFEPATH=1
TZ=UTC
```

All other variables are absent. In particular, `PATH`, `HOME`, `PYTHONPATH`,
`PYTHONHOME`, `PYTHONUSERBASE`, `VIRTUAL_ENV`, loader variables, proxies,
certificate overrides, Git variables, and additional locale variables cannot
influence execution.

## Package integration

The unindexed successor root is:

```text
authorizations/{authorization_identity}/execution_runtime_package_v010.json
```

It reaches exactly:

```text
runtime/{authorization_identity}/execution_runtime_descriptor_v010.json
runtime/{authorization_identity}/execution_runtime_inventory_v010.json
```

Those are the three V010-owned paths, not the complete composite package. The
complete package root is the disjoint union of the independently validated
V006, V007, and V009 package projections, the packaged V008 bootstrap/history
material governed by V008 and V009, and this exact V010 projection. Existing
predecessor closed worlds remain intact, and no path may be unowned or owned by
two versions.

It binds one V006 operator package, V007 runtime package, V008 continuation
identity, and V009 documentary-proof package. It carries two exact V006
successor-index entries and two V007 supplemental-manifest entries without
mutating the sealed predecessors. Authorization and operator identities bind it
transitively to V008. Missing, duplicate, alternate, unindexed, unreachable,
cross-package, cross-operator, cross-command, or cross-version material rejects.

The descriptor, inventory, and package share a package-binding identity over
the predecessor-package, authorization, operator, command, and V010 identities.
Only the package identity includes descriptor and inventory identities, avoiding
a self-referential hash cycle.

A separate runtime-content identity covers the root path and metadata, import
roots, directories, files, Mach-O edges, dyld cache files, platform images, and
prohibited-artifact state without authorization-specific fields. The
package-environment identity combines that content identity with the derived
dependency lock, platform, Python, ABI, and architecture. This cycle-free
identity can be approved before the V005 authorization identity exists; the
authorization-specific descriptor and inventory are created afterward.

V005 remains byte-for-byte unchanged. Its authorization still contains the
historical command as required by the frozen schema, but a V010 package may not
execute that command. The fully validated V005 authorization's environment
manifest package-lock field must equal the full V010 package-environment
identity and must match the
descriptor's architecture and Python version. Its environment allowlist must
also equal all seven V010 assignments exactly. That bridge makes the dependency
lock, complete runtime content, platform, Python, and environment part of the
approved V005 graph; V010 then
deterministically requires its successor command. V010 neither creates nor
infers human approval: the exact future single-use authorization package and
V010 records still require the existing independent review before activation.

## Mandatory preflight order

1. Validate V010 and frozen lineage.
2. Validate the V010 package root and closed world.
3. Validate the V005 authorization/environment-to-V010 package-environment bridge.
4. Validate the successor command and resolved arguments.
5. Validate the runtime descriptor.
6. Validate inventory and dependency closure.
7. Validate the preflight authorized-source closed world.
8. Validate the pre-execution runtime observation.
9. Validate source/runtime separation.
10. Validate the exact environment.
11. Validate the point-of-exec source observation.
12. Validate the point-of-exec runtime observation.
13. Validate the exact post-bootstrap Python import path.
14. Validate V009 documentary-proof transport.
15. Publish the V008 invocation claim.
16. Acquire entropy and the AF_UNIX clock connection.
17. Validate V007 repository evidence using independent trusted time.
18. Publish the V005 activation transition.

No entropy, socket, authorization mutation, or lifecycle transition may occur
before the first fourteen non-mutating checks pass.

## Fail-closed model

Schema, identity, command, source, ordinary inventory, ownership, mode, path,
environment, and substitution defects are rejections. An absent or unreadable
descriptor/root is unavailable. Dependency closure, resource exhaustion,
attestation availability, runtime mutation, and point-of-use continuity
uncertainty are indeterminate. Indeterminate continuity takes precedence and
never succeeds. The canonical contract maps every required condition to its
exact class and code. Runtime freshness expiry is explicitly inapplicable: this
static package has no clock-validity window, and any observed change is a
runtime-mutation or continuity-indeterminate failure.

## Authority boundary

V005 remains the exclusive authorization and lifecycle authority. V006 remains
the operator-interface and historical-command authority. V007 remains the
runtime-transport, repository, and implementation-identity authority. V008
remains clock continuation and replay authority. V009 remains documentary-proof
transport authority. V010 governs only runtime placement, identity, command
supersession, source/runtime separation, and runtime preflight.

V010 creates no runtime, launcher, operator, verifier, attestor, authorization,
execution, result, or trading capability.

## Frozen identity

- Outer identity: `1f61ef16f1e843de01cf7dcebad357ee4bfd7c16191c71270fa7ae97bb9c326a`
- Successor-command identity: `f9d7923bf58a6055e2276d4bdbe4c474f5c0ab7d7d6752dabc7648461fb04c75`
- Canonical contract size: 28,837 bytes
- Contract file SHA-256: `87d78df1d7c39d90a4e2ff72693dedd3e0d8e2d02e7ddc4e2676a2d6764a973c`

Section identities:

```text
inheritance                 53019322624541c6a47ac4f063dadd17e0c73c15178771f4348139ef7672398a
contradiction_resolution    b3f1f50bfb28b4498c70b9fd24a6ec6b9b655613fb0f5274672e4c7f2560c2f8
runtime_placement           ddb10b75c09a399c15d60d0c931016a325e03e79a2355bcbeb19bdf294e3e99a
command_supersession        6393f44432e6ff144527ea075175b263ed00ebef7890ff87b570f5a96f1f023a
runtime_schemas             3142a97e7888edf1c18e7ee4ffce012d032a050d9dbbf6cff8111cb30b25becb
runtime_inventory           89ab4ec2926eab286df1e8907b1955fcb262fcf78e7acff5fd47ad8fa0cd3b61
dependency_closure          f6c64cd77b461b83daa2231c5ecd11ca22edd88ca6c117ba64170eff5cb831c4
virtual_environment         be3d0e9fc90877c7489984c2edf927138f149809563ab4d66243041ade97a0c3
source_boundary             849873b0a376f692b9727c50c796c3c71b8216a0ce8d1d7a2c13b030391f685e
source_runtime_separation   2b643b139886823e80e0fa8bd21864910ae669cf9fd70650a7ebbf596c1c9ed2
launch_semantics            85983f9d1b37234fcc2c32ef89fda4c1cf2c344a000eb2a2cb143a185a963dc2
environment_closure         a275b1eff92c4c7352385eeed3cd06c30aae2323bd7d9ccf1cce0f4c9a0c1782
package_integration         c72acc8f28fecce8bdabff91f3f38e6e58f22a690f3461cfaae8ee32d7d28727
preflight_order             c62b72acb4d95197e81941b7ddaa2e254184636224099305a9543e0ea7868f54
error_status_model          ded03439466f760703ae813b6beba274d79283fdb4b3985ec58c08fcd2360a07
authority_boundary          eee5186eeb1e2c273a360850d8f733867071f7f38c5de151df2685f2ead83c7a
validation_manifest         1c3b20abc9c7618206d9cd1f9f32a132a548bfe1336b133aaab6d95e889f2f48
```

## Verification

```bash
PYTHONPATH=src .venv/bin/python scripts/validate_professional_strategy_olympics_execution_runtime_v010.py --root .
PYTHONPATH=src .venv/bin/python -m pytest tests/test_professional_strategy_olympics_execution_runtime_v010.py
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
git diff --check
```
