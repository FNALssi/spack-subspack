import os
import glob
import re
import shutil
import time
from collections import OrderedDict
from contextlib import contextmanager

import spack.config
import spack.util.path

try:
    import spack.llnl.util.tty as tty
    import spack.llnl.util.filesystem as fs
except:
    import llnl.util.tty as tty
    import llnl.util.filesystem as fs
import spack.util.spack_yaml as syaml
import spack.util.path
import spack.util.git
import spack.extensions
import spack.repo
from spack.store import parse_install_tree

config = spack.config.CONFIG


def make_subspack(args):
    """find prefix, call sub-steps"""
    prefix = spack.util.path.canonicalize_path(args.prefix)
    tty.debug("Cloning spack repo...")
    quick_clone(prefix, args)
    tty.debug("Cloning extensions...")
    quick_clone_ext(prefix, args)
    tty.debug("Cloning repos... here")
    quick_clone_repos(prefix, args)
    tty.debug("Merging upstreams files...")
    merge_upstreams(prefix, args)
    tty.debug("Cloning configs...")
    clone_various_configs(prefix, args)
    tty.debug("symlinking environments:")
    symlink_environments(prefix, args)
    tty.debug("making local_xxx environments:")
    copy_local_environments(prefix, args)
    tty.debug("adding wrapped setup-env.* scripts:")
    add_local_setup_env(prefix, args)
    tty.debug("adding padding if requested")
    add_padding(prefix, args)
    add_upstream(prefix, args.add_upstream)


def add_upstream_origin(src, dest):
    """if the upstream repository at src has an "origin", add it to the repostory at dest as "upstream_origin" """
    path = None
    git = spack.util.git.git(required=True)
    with fs.working_dir(src):
        with os.popen("git remote -v") as gitout:
            for line in gitout:
                repo, path, direction = re.split("\s+", line.strip())
                if repo == "origin":
                    break
    if path:
        with fs.working_dir(dest):
            git("remote", "add", "upstream_origin", path)
    return path


def add_upstream(prefix, spack_roots):
    # get current upstreams
    with open(f"{prefix}/etc/spack/upstreams.yaml", "r") as f:
        upstream_data = syaml.load(f)

    count = 0
    for r in spack_roots:
        tty.debug("adding upstream: ", r)

        count = count + 1

        # read config.yaml data from desired upstream
        cmd = f"SPACK_ROOT={r} spack config get config"
        with os.popen(cmd, "r") as f:
            upstream_config = syaml.load(f)

        upstream_inst_root = upstream_config["config"]["install_tree"]["root"].replace(
            "$spack", r
        )
        if (
            upstream_config.get("modules", {})
            .get("default", {})
            .get("roots", {})
            .get("tcl", "")
        ):
            tcl_modules = upstream_config["modules"]["default"]["roots"]["tcl"].replace(
                "$spack", r
            )
        else:
            tcl_modules = f"{r}/share/spack/modules"

        upstream_data["upstreams"][f"spack_{count}"] = {
            "install_tree": upstream_inst_root,
            "modules": {"tcl": tcl_modules},
        }

    with open(f"{prefix}/etc/spack/upstreams.yaml", "w") as f:
        syaml.dump(upstream_data, f)


def add_padding(prefix, args):
    """turn on standard Fermi build-instance padding"""
    if args.with_padding:
        with open(f"{prefix}/etc/spack/config.yaml", "w") as fco:
            fco.write("config:\n  install_tree:\n    padded_length: 128\n")


def quick_clone(prefix, args):
    """clone the spack repo, shallow etc."""
    if args.remote_branch:
        branch = args.remote_branch
    else:
        branch = None
    git = spack.util.git.git(required=True)
    cleanup = None
    if not args.remote:
        args.remote = os.environ["SPACK_ROOT"] + "/.git"
        git("config", "--global", "--add", "safe.directory", args.remote)
        cleanup = args.remote

    if args.remote.startswith("/") and not branch:
        with os.popen(f"cd {args.remote} && git branch | grep '\\*'") as bf:
            branch = bf.read().strip(" *\n")
        args.remote = "file://" + args.remote

    git_args = ["clone", "-q", "--depth", "2", args.remote, prefix]
    if branch:
        git_args[1:1] = ["-b", branch]
    tty.debug(f"Cloning with: git {' '.join(git_args)}")
    git(*git_args)

    if cleanup:
        git("config", "--global", "--unset", "safe.directory", cleanup)

    if args.remote and args.remote.startswith("file://"):
        add_upstream_origin(args.remote[7:], prefix)


def quick_clone_repos(prefix, args):
    """clone the other recipe repositories"""
    tty.debug(f"quick_clone_repos: starting")
    git = spack.util.git.git(required=True)
    roots = spack.config.get("repos", scope=None)
    repos = []
    tty.debug(f"quick_clone_repos: roots: {repr(roots)}")

    if isinstance(roots, dict):
        tty.debug("dict case")
        for repo_name in roots:
            tty.debug(f"repo {repo_name}")
            tty.debug(f"roots[repo_name] is {repr(roots[repo_name])}")
            branch = roots[repo_name]["branch"]
            base = repo_name
            if isinstance(roots[repo_name], dict):
                dest = roots[repo_name]["destination"]
            else:
                dest = roots[repo_name]
            src = dest.replace("$spack", os.environ["SPACK_ROOT"])
            dest = dest.replace("$spack", prefix).replace(
                os.environ["SPACK_ROOT"], prefix
            )
            if os.path.exists(f"{src}/.git"):
                tty.debug("cloning {src} to {dest}")
                git("config", "--global", "--add", "safe.directory", f"{src}/.git")
                git(
                    "clone",
                    "-q",
                    "--depth",
                    "2",
                    "-b",
                    branch,
                    f"file://{src}/.git",
                    dest,
                )
                git("config", "--global", "--unset", "safe.directory", f"{src}/.git")
                upath = add_upstream_origin(src, dest)
                if args.update_recipes and upath:
                    with fs.working_dir(dest):
                        git("pull", "upstream_origin", branch)

            else:
                tty.debug(f"symlinking {src} to {dest}")
                # non-git repo, and not already there, symlink it?
                os.symlink(src, dest)
    else:
        tty.debug("else case")
        for r in roots:
            repos.append(r)
        for repo in repos:
            src = str(repo)
            repo = src.replace("$spack", os.environ["SPACK_ROOT"])
            base = os.path.basename(repo)
            dest = f"{prefix}/var/spack/repos/{base}"
            if os.path.exists(f"{repo}/.git"):
                git("config", "--global", "--add", "safe.directory", f"{repo}")
                git("clone", "-q", "--depth", "2", f"file://{repo}", dest)
                git("config", "--global", "--unset", "safe.directory", f"{repo}")
            elif not os.path.exists(dest):
                # non-git repo, and not already there, symlink it?
                os.symlink(src, dest)

    # write new repo config
    tty.debug(f"quick_clone_repos: writing {prefix}/etc/spack/repos.yaml")
    repos = {"repos": roots}
    with open(f"{prefix}/etc/spack/repos.yaml", "w") as f:
        syaml.dump(repos, f)


def quick_clone_ext(prefix, args):
    git = spack.util.git.git(required=True)
    extensions = spack.extensions.get_extension_paths()
    for path in extensions:
        base = os.path.basename(path)
        if os.path.exists(f"{path}/.git"):
            dest = f"{prefix}/var/spack/extensions/{base}"
            git("config", "--global", "--add", "safe.directory", f"{path}/.git")
            git("clone", "-q", "--depth", "2", f"file://{path}/.git", dest)
            git("config", "--global", "--unset", "safe.directory", f"{path}/.git")
            upath = add_upstream_origin(path, dest)
            if args.update_extensions and upath:
                with fs.working_dir(path):
                    with os.popen("git branch --show-current") as fin:
                        branch = fin.read().strip()
                with fs.working_dir(dest):
                    git("pull", "upstream_origin", branch)

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
        itree = parse_install_tree(config.get("config"))
        upstream_inst_root = itree[0]

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
        # interleaved pack/conf/comp/incl
        pattern = "[pci][aon][cmn][kfpl]*.yaml"
    else:
        # interleaved pack/conf/comp/mirr/incl
        pattern = "[ipcm][aoin][cmnr][lkfpr]*.yaml"

    os.system(
        f"""
        cd $SPACK_ROOT &&
        find etc/spack -name {pattern} -print |
           cpio --quiet -dump {prefix}
    """
    )

    # also make sure there is an etc/spack/base directory
    basedir = f"{prefix}/etc/spack/base"
    if not os.path.isdir(basedir):
        os.mkdir(basedir)

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
