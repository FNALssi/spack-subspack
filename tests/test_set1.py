
import os
import sys
sys.path.append(os.path.join(os.environ["SPACK_ROOT"], "lib", "spack"))
sys.path.append(os.path.join(os.environ["SPACK_ROOT"], "lib", "spack", "external"))
sys.path.append(os.path.join(os.environ["SPACK_ROOT"], "lib", "spack", "external", "_vendoring"))
prefix=os.path.dirname(os.path.dirname(__file__))
sys.path.append(os.path.join(prefix, "subspack"))

import spack.main
import subspack
import llnl.util.tty as tty

tty.set_verbose(1)
tty.set_debug(1)
tty.set_stacktrace(1)


class fakeargs:

    def __init__(self, *args):
        self.prefix, self.local_env, self.dev_pkg, self.remote = args

def test_make_subspack():
    args = fakeargs("/tmp/foo", ["env1"], ["watch"], os.environ["SPACK_ROOT"]+"/.git")
    os.system(f"rm -rf {args.prefix}")
    os.system("spack env create env1")
    os.system("spack --env env1 install --add watch")
    subspack.make_subspack(args)


