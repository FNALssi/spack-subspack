

## Spack-subspack

Tool to maked "subspack" instances; a new spack area which
is connected via "upstream.yaml" configs ton an existing spack
area, generally for development, adding extra packages, etc.

This includes:
* cloning relevant config files
* attaching the curent spack instance as an upstream
* symlinking existing environments in the new instance

### Usage

In most cases you can just do:

  spack subspack /destination/directory

but there are a few option flags that are often useful
  
* --with_padding includes 'padded_width: 255' in the config.yaml of the new instance
* --local-env environment_name  besides the usual symlinking of environments in the subspack, copy the environment "environment_name" as "local_environment_name" (i.e with the prefix "local_") 
* --dev-pkg pkg  Run a spack develop pkg in the local environment copies, above; can be repeated for multiple packages.  Should usually include pkg@develop or pkg@master version tags.

