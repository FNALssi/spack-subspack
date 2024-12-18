import os
import glob
import sys
import time
import pytest

#
# update sys.path so that spack imports  work...
#
sys.path.append(os.path.join(os.environ["SPACK_ROOT"], "lib", "spack"))
sys.path.append(os.path.join(os.environ["SPACK_ROOT"], "lib", "spack", "external"))
sys.path.append(
    os.path.join(os.environ["SPACK_ROOT"], "lib", "spack", "external", "_vendoring")
)

import spack.main
import llnl.util.tty as tty

#
# update sys.path so *our* imports work...
#
prefix = os.path.dirname(os.path.dirname(__file__))
sys.path.append(os.path.join(prefix, "subspack"))

import subspack

#
# initialize spack tty / logging module for verbose/debug
#
tty.set_verbose(1)
tty.set_debug(1)
tty.set_stacktrace(1)


def test_tmp_env():
    """check our 'with tmp_env()...' bits.."""

    os.environ["XXX"] = "a"
    assert os.environ["XXX"] == "a"
    with subspack.tmp_env("XXX", "b"):
        assert os.environ["XXX"] == "b"
    assert os.environ["XXX"] == "a"


class fakeargs:
    """class to use for argparsed args..."""

    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)


# datestamp for start of this test...
ds = int(time.time())


@pytest.fixture
def args1():
    return fakeargs(
        prefix=f"/tmp/dstrepo{ds}",
        remote=f"/tmp/srcrepo{ds}",
        with_padding=False,
    )


@pytest.fixture
def scratch_repo1(args1):
    os.mkdir(args1.remote)
    for f in ("a", "b"):
        with open(os.path.join(args1.remote, f), "w") as fd:
            fd.write("hello")
    os.system(f"cd {args1.remote} && git init && git add * && git commit -am test")
    os.system(f"ls -l {args1.remote}")
    yield args1
    # clean them back up...
    os.system(f"rm -rf {args1.remote}")
    os.system(f"rm -rf {args1.prefix}")


def test_quick_clone(scratch_repo1):
    args = scratch_repo1
    subspack.quick_clone(args.prefix, args)
    assert os.path.exists(f"{args.prefix}/a")
    assert os.path.exists(f"{args.prefix}/b")
    assert os.path.exists(f"{args.prefix}/.git")


@pytest.fixture
def args2():
    return fakeargs(
        prefix=f"/tmp/foo{ds}",
        local_env=[f"env1{ds}"],
        dev_pkg=["watch@master"],
        remote=os.environ["SPACK_ROOT"] + "/.git",
        with_padding=False,
    )


@pytest.fixture
def testenv(args2):
    os.system(f"rm -rf {args2.prefix}")
    os.system(f"spack env create {args2.local_env[0]} > /dev/null")
    os.system(f"spack --env {args2.local_env[0]} install --add watch > /dev/null")
    yield args2
    os.system(f"spack env remove {args2.local_env[0]} >  /dev/null")


def test_make_subspack(testenv):
    """Full integration test:
    this assumes we have a spack environment currently...
    """
    args = testenv

    subspack.make_subspack(args)
    spack_root = args.remote.replace("/.git", "")

    df = f"{args.prefix}/etc/spack/upstreams.yaml"
    print(f"checking for {df}")
    assert os.path.exists(df)
    for f in glob.glob(f"{spack_root}/etc/spack/**/[pc][ao][cm]*.yaml", recursive=True):
        df = f.replace(spack_root, args.prefix)
        print(f"Checking for {f} -> {df}")
        assert os.path.exists(df)
