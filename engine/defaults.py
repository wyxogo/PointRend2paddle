from omegaconf import OmegaConf
import os
import logging
import numpy as np
import random
from datetime import datetime
import paddle
from typing import List

# import utils.comm as comm
from utils.cfg_node import CfgNode
from utils.path_manager import PathManager
from utils.logger import setup_logger 
from utils.lazy import LazyConfig


def seed_all_rng(seed=None):
    """
    Set the random seed for the RNG in torch, numpy and python.

    Args:
        seed (int): if None, will use a strong random seed.
    """
    if seed is None:
        seed = (
            os.getpid()
            + int(datetime.now().strftime("%S%f"))
            + int.from_bytes(os.urandom(2), "big")
        )
        logger = logging.getLogger(__name__)
        logger.info("Using a generated random seed {}".format(seed))
    np.random.seed(seed)
    paddle.seed(seed)
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

def _highlight(code, filename):
    try:
        import pygments
    except ImportError:
        return code
    from pygments.lexers import Python3Lexer, YamlLexer
    from pygments.formatters import Terminal256Formatter

    lexer = Python3Lexer() if filename.endswith(".py") else YamlLexer()
    code = pygments.highlight(code, lexer, Terminal256Formatter(style="monokai"))
    return code
def _try_get_key(cfg, *keys, default=None):
    """
    Try select keys from cfg until the first key that exists. Otherwise return default.
    """
    if isinstance(cfg, CfgNode):
        cfg = OmegaConf.create(cfg.dump())
    for k in keys:
        # OmegaConf.select(default=) is supported only after omegaconf2.1,
        # but some internal users still rely on 2.0
        parts = k.split(".")
        # https://github.com/omry/omegaconf/issues/674
        for p in parts:
            if p not in cfg:
                break
            cfg = OmegaConf.select(cfg, p)
        else:
            return cfg
    return default

def default_setup(cfg, args):
    output_dir = _try_get_key(cfg, "OUTPUT_DIR", "output_dir", "train.output_dir")
    if  output_dir:
        PathManager.mkdirs(output_dir)

    # rank = comm.get_rank()
    setup_logger(output_dir, name="PointRend")
    logger = setup_logger(output_dir)

    # logger.info("Rank of current process: {}. World size: {}".format(rank, comm.get_world_size()))
    # logger.info("Environment info:\n" + collect_env_info())

    # logger.info("Command line arguments: " + str(args))
    # if hasattr(args, "config_file") and args.config_file != "":
    #     logger.info(
    #         "Contents of args.config_file={}:\n{}".format(
    #             args.config_file,
    #             _highlight(PathManager.open(args.config_file, "r").read(), args.config_file),
    #         )
    #     )

    if output_dir:
        # Note: some of our scripts may expect the existence of
        # config.yaml in output directory
        path = os.path.join(output_dir, "config.yaml")
        if isinstance(cfg, CfgNode):
            logger.info("Running with full config:\n{}".format(_highlight(cfg.dump(), ".yaml")))
            with PathManager.open(path, "w") as f:
                f.write(cfg.dump())
        else:
            LazyConfig.save(cfg, path)
        logger.info("Full config saved to {}".format(path))

    # make sure each worker has a different, yet deterministic seed if specified
    seed = _try_get_key(cfg, "SEED", "train.seed", default=-1)
    seed_all_rng(None if seed < 0 else seed + 1)