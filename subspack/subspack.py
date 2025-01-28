import os
import glob
import shutil
import time
from contextlib import contextmanager

import spack.config
import spack.util.path
import llnl.util.tty as tty
import spack.util.spack_yaml as syaml
import spack.util.path
import spack.util.git
import spack.extensions
import spack.repo

config = spack.config.CONFIG


def make_subspack(args):
    """find prefix, call sub-steps"""
    prefix = spack.util.path.canonicalize_path(args.prefix)
    tty.debug("Cloning spack repo...")
    quick_clone(prefix, args)
    tty.debug("Cloning extensions...")
    quick_clone_ext(prefix, args)
    tty.debug("Cloning repos...")
    quick_clone_repos(prefix, args)
    tty.debug("Merging upstreams files...")
    merge_upstreams(prefix, args)
    tty.debug("Cloning configs...")
    clone_various_configs(prefix, args)
    tty.debug("symlinking environments:")
    symlink_environments(prefix, args)
    tty.debug("making local_xxx environments:")
    copy_local_environments(prefix, args)
    tty.debug("adding wrapped setup-env.* scritsp:")
    add_local_setup_env(prefix, args)
    tty.debug("adding padding if requested")
    add_padding(prefix, args)


def add_padding(prefix, args):
    """turn on standard Fermi build-instance padding"""
    if args.with_padding:
        with open(f"{prefix}/etc/spack/config.yaml", "w") as fco:
            fco.write("config:\n  install_tree:\n    padded_length: 255\n")


def quick_clone(prefix, args):
    """clone the spack repo, shallow etc."""
    if args.remote_branch:
        branch = args.remote_branch
    else:
        branch = None
    git = spack.util.git.git(required=True)
    if not args.remote:
        args.remote = os.environ["SPACK_ROOT"] + "/.git"
        git("config", "--global", "--add", "safe.directory", args.remote)

    if args.remote.startswith("/") and not branch:
        with os.popen(f"cd {args.remote} && git branch | grep '\\*'") as bf:
            branch = bf.read().strip(" *\n")
        args.remote = "file://" + args.remote

    args = ["clone", "-q", "--depth", "2", args.remote, prefix]
    if branch:
        args[1:1] = ["-b", branch]
    tty.debug(f"Cloning with: git {' '.join(args)}")
    git(*args)


def quick_clone_repos(prefix, args):
    """clone the other recipe repositories"""
    git = spack.util.git.git(required=True)
    roots = spack.config.get("repos", scope=None)
    repos = []
    for r in roots:
        repos.append(r)
    for repo in repos:
        repo = str(repo)
        repo = repo.replace('$spack', os.environ['SPACK_ROOT'])
        base=os.path.basename(repo)
        dest = f"{prefix}/var/spack/repos/{base}"
        if os.path.exists(f"{repo}/.git"):
            git("clone", "-q", "--depth", "2", f"file://{repo}", dest)
        elif not os.path.exists(dest):
            # non-git repo, and not already there, symlink it?
            os.symlink(repo, dest)


def quick_clone_ext(prefix, args):
    git = spack.util.git.git(required=True)
    extensions = spack.extensions.get_extension_paths()
    for path in extensions:
        base = os.path.basename(path)
        if os.path.exists(f"{path}/.git"):
            dest = f"{prefix}/var/spack/extensions/{base}"
            git("clone", "-q", "--depth", "2", f"file://{path}", dest)
        elif not os.path.exists(dest):
            # non-git repo, and not already there, symlink it?
            os.symlink(path, dest)


def merge_upstreams(prefix, args):
    """generate upstreams.yaml pointing to us including
    any upstreams we have"""
    # start with our upstreams, if any...
    upstream_data = config.get("upstreams", None)
    tty.debug(f"Got upstream data: {repr(upstream_data)}")
    if upstream_data is None:
        upstream_data = {"upstreams": {}}
    else:
        upstream_data = {"upstreams": upstream_data}

    upstream_inst_root = config.get("config:install_tree:root").replace(
        "$spack", os.environ["SPACK_ROOT"]
    )

    if config.get("config:install_tree:padded_length", 0) > 0:
        # find __...padded directories add to upstream_inst_root...
        pass

    tcl_modules = config.get(
        "modules:default:roots:tcl", f"{prefix}/share/spack/modules"
    )

    ds = str(time.time())
    upstream_data["upstreams"][f"spack_{ds}"] = {
        "install_tree": upstream_inst_root,
        "modules": {"tcl": tcl_modules},
    }

    with open(f"{prefix}/etc/spack/upstreams.yaml", "w") as f:
        syaml.dump(upstream_data, f)


@contextmanager
def tmp_env(var, val):
    """routine to use as 'with tmp_env("VAR",value):...' that puts it back afterwards"""
    save = os.environ[var]
    os.environ[var] = val
    yield val
    os.environ[var] = save


def clone_various_configs(prefix, args):
    """clone config files"""
    # clone packages, compilers...
    # the -name arg is boot*.yaml pack*.yaml comp*.yaml interleaved..
    # sorry, some things are just easier in shell...
    if args.without_caches:
        # interleaved pack/conf/comp
        pattern="[pc][ao][cmn][kfp]*.yaml"
    else:
        # interleaved pack/conf/comp/mirr
        pattern="[pcm][aoi][cmnr][kfpr]*.yaml"

    os.system(
        f"""
        cd $SPACK_ROOT &&
        find etc/spack -name {pattern} -print |
           cpio --quiet -dump {prefix}
    """
    )

    root = spack.config.get("bootstrap:root", default=None)
    if root:
        root = spack.util.path.canonicalize_path(root)

    with tmp_env("SPACK_ROOT", prefix):
        os.system(f"{prefix}/bin/spack bootstrap root {root} > /dev/null")


def symlink_environments(prefix, args):
    """add symlinks to upstream environments so we have them"""
    env_list = glob.glob(f"{os.environ['SPACK_ROOT']}/var/spack/environments/*")
    # symlink upstream environments

    ed = f"{prefix}/var/spack/environments/"
    if not os.path.exists(ed):
        os.mkdir(ed)

    for e in env_list:
        base = os.path.basename(e)
        os.symlink(e, f"{ed}/{base}")

    repos = {"repos": config.get("repos")}
    with open(f"{prefix}/etc/spack/repos.yaml", "w") as f:
        syaml.dump(repos, f)


def copy_local_environments(prefix, args):
    """make local_xxx environments requested in our args"""
    # copy local environments
    for base in args.local_env:
        tty.debug("making local_{base} for {base}")
        srcd = f"{os.environ['SPACK_ROOT']}/var/spack/environments/{base}"
        dstd = f"{prefix}/var/spack/environments/local_{base}"
        if os.path.exists(srcd):
            os.mkdir(dstd)
            for f in ["spack.yaml", "spack.lock"]:
                fp = f"{srcd}/{f}"
                lfp = f"{dstd}/{f}"
                if os.path.exists(fp):
                    shutil.copyfile(fp, lfp)
        else:
            tty.error(f"No source environment {base}")

        # mark packages develop; do this in in the
        # other spack instance...
        with tmp_env("SPACK_ROOT", prefix):
            for p in args.dev_pkg:
                os.system(f"{prefix}/bin/spack --env local_{base} develop {p}")


def add_local_setup_env(prefix, args):
    with open(f"{prefix}/setup-env.sh", "w") as shf:
        shf.write(
            f"""
export SPACK_SKIP_MODULES=true
export SPACK_DISABLE_LOCAL_CONFIG=true
. {prefix}/share/spack/setup-env.sh
"""
        )
    with open(f"{prefix}/setup-env.csh", "w") as shf:
        shf.write(
            f"""
setenv SPACK_SKIP_MODULES true
setenv SPACK_DISABLE_LOCAL_CONFIG true
source {prefix}/share/spack/setup-env.sh
"""
        )
