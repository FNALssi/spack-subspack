import os
import glob
import shutil
import time

import spack.config
import spack.util.path
import llnl.util.tty as tty
import spack.util.spack_yaml as syaml


config = spack.config.CONFIG

def make_subspack(args):
    """ find prefix, call sub-steps"""
    prefix = spack.util.path.canonicalize_path(args.prefix)
    print("calling quick_clone:")
    quick_clone(prefix, args)
    print("calling merge_upstreams:")
    merge_upstreams(prefix,args)
    print("calling various configs:")
    clone_various_configs(prefix, args)
    symlink_environments(prefix,args)
    copy_local_environments(prefix,args)
    add_local_setup_env(prefix,args)

def quick_clone(prefix, args):
    if not args.remote:
         args.remote = os.environ["SPACK_ROOT"] + "/.git"
    
    with os.popen(f"cd $SPACK_ROOT && git branch | grep '\\*'") as bf:
         branch = bf.read().strip().strip('*')
    cmd = f"git clone -b {branch} {args.remote} {prefix}"
    print(f"Cloning with: {cmd}")
    os.system( cmd )

def merge_upstreams(prefix, args):
    """ generate upstreams.yaml pointing to us including
        any upstreams we have """
    # start with our upstreams, if any...
    upstream_data = config.get("upstreams", None)
    print(f"Got upstream data: {repr(upstream_data)}")
    if upstream_data is None:
        upstream_data = { "upstreams": {} }
    else:
        upstream_data = { "upstreams": upstream_data }

    upstream_inst_root = ( 
           config.get("config:install_tree:root")
              .replace("$spack",os.environ["SPACK_ROOT"])
    )

    if config.get("config:padded_length",0) > 0:
        # find __...padded directories add to upstream_inst_root...
        pass

    tcl_modules = config.get(
       "modules:default:roots:tcl", 
       f"{prefix}/share/spack/modules"
    )
        
    ds=str(time.time())
    upstream_data["upstreams"][f"spack_{ds}"] = {
         "install_tree": upstream_inst_root,
         "modules": { "tcl": tcl_modules },
      }

    with open(f"{prefix}/etc/spack/upstream.yaml", "w") as f:
        syaml.dump(upstream_data, f)

def clone_various_configs(prefix, args):
    """ clone config files """
    # clone packages, compilers...
    # the -name arg is boot*.yaml pack*.yaml comp*.yaml interleaved..
    # sorry, some things are just easier in shell...
    os.system(f""" 
        cd $SPACK_ROOT && 
        find etc/spack -name [bpc][oao][ocm][tkp]*.yaml -print |
           cpio -dump {prefix}
    """)

def symlink_environments(prefix, args):
    """ add symlinks to upstream environments so we have them """
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
    """ make local_xxx environments requested in our args """
    # copy local environments
    for base in args.local_env:
        srcd = f"{prefix}/var/spack/environments/{base}"
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
        os.environ["SPACK_ROOT"] = prefix
        for p in args.dev_pkg:
            os.system(f"{prefix}/bin/spack --env local_{base} develop {p}@develop")
    
def add_local_setup_env(prefix,args):
     with open(f"{prefix}/setup-env.sh", "w") as shf:
         shf.write(f"""
export SPACK_SKIP_MODULES=true
export SPACK_DISABLE_LOCAL_CONFIG=true
. {prefix}/share/spack/setup-env.sh
""")
     with open(f"{prefix}/setup-env.csh", "w") as shf:
         shf.write(f"""
setenv SPACK_SKIP_MODULES true
setenv SPACK_DISABLE_LOCAL_CONFIG true
source {prefix}/share/spack/setup-env.sh
""")

