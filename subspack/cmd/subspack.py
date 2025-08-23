import sys
import spack.config
from spack.extensions import subspack as subspackext

description = "make a development spack with current spack as upstream"
section = "basic"
level = "short"


def setup_parser(subparser):

    scopes = spack.config.scopes()

    subparser.add_argument(
        "--without-caches",
        "--without_caches",
        action="store_true",
        default=False,
        help="omit mirrors.yaml copies to subpack instance",
    )
    subparser.add_argument(
        "--with-padding",
        "--with_padding",
        action="store_true",
        default=False,
        help="include diretory padding in config",
    )
    subparser.add_argument(
        "--local-env",
        "--local_env",
        action="append",
        default=[],
        help="environment(s) to make local versions of",
    )
    subparser.add_argument("--remote", default=None, help="git remote to clone from")
    subparser.add_argument(
        "--dev-pkg",
        "--dev_pkg",
        action="append",
        default=[],
        help="packages to setup with spack develop",
    )
    subparser.add_argument(
        "--add-upstream",
        action="append",
        default=[],
        help="additional spack instances to add as upstreams",
    )
    subparser.add_argument(
        "prefix",
        help="location of new subspack instance",
    )


def subspack(parser, args):
    # print("parser is " + repr(parser) + "args: " + repr(args))
    subspackext.make_subspack(args)
