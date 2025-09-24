import json
import os
import uuid

def save_info_meta_conf(wmo: str, ptt: str, directories:dict, info: dict, meta: dict, decoder_conf: dict):
    """
    Save info and meta dictionaries into float-specific UUID directories.

    Parameters:
		wmo (str): WMO identifier for the float.
		ptt (str): PTT identifier for the float.
        directories (dict): Dictionary containing paths for 'json_float_info' and 'json_float_meta'.
        info (dict): Info dictionary to save.
        meta (dict): Meta dictionary to save.
        decoder_conf (dict): Decoder configuration dictionary to save.
    """

    # Ensure directories exist
    os.makedirs(directories["json_float_info"], exist_ok=True)
    os.makedirs(directories["json_float_meta"], exist_ok=True)
    os.makedirs(directories["config"], exist_ok=True)


    if not wmo or not ptt:
        raise ValueError("info dictionary must contain 'WMO' and 'PTT' keys")

    # File paths
    info_file = os.path.join(directories["json_float_info"], f"{wmo}_{ptt}_info.json")
    meta_file = os.path.join(directories["json_float_meta"], f"{wmo}_meta.json")
    conf_file = os.path.join(directories["config"], "decoder_conf.json")

    # Write info
    with open(info_file, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=4)

    # Write meta
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=4)

    # Write decoder_conf
    with open(conf_file, "w", encoding="utf-8") as f:
        json.dump(decoder_conf, f, indent=4)

    return {
        "info_file": info_file,
        "meta_file": meta_file,
        "conf_file": conf_file,
    }
