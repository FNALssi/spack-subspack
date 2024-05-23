import sys
import spack.config
from  spack.extensions import subspack as sext

def setup_parser(subparser):

    scopes = spack.config.scopes()

    subparser.add_argument(
        "--with-padding",
        action="store_true",
        default=False,
        help="include diretory padding in config",
    )
    subparser.add_argument(
        "--local-env",
        action="append",
        default = []
        help="environment(s) to make local versions of"
    )
    subparser.add_argument(
        "--dev-pkg",
        action="append",
        default = []
        help="packages to setup with spack develop"
    )
    subparser.add_argument(
        "prefix",
        help="location of new subspack instance",
    )

    
def subspack(parser, args):
    #print("parser is " + repr(parser) + "args: " + repr(args))
    sext.make_subspack(args)
