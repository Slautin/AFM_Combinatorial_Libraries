import numpy as np

from afm_lib.config import cache_dir
from afm_lib.readers.scifireaders_service import SciFiReadersService
from afm_lib.states.analysis_state import AnalysisState
from afm_lib.utils.channel_utils import save_array, save_preview, get_stats, fix_units
from afm_lib.utils.loops_utils import classify_measurement

ORIENT_K = 1        # rot90 count for 2-D channels; a no-op for 1-D loop traces


async def readfile_node(state: AnalysisState) -> AnalysisState:
    """Read an SPM file and prepare channel metadata, stats, and preview paths.

    Artifacts land in cache_dir()/<out_stem> so that measurements in a grid run do
    not overwrite each other's arrays and previews."""
    file_path = state["file_path"]
    dest = cache_dir() / state.get("out_stem", "current")

    channels = {}
    ch_keys = ['title', 'units', 'data_type', 'shape']

    service = SciFiReadersService()
    payload = await service.read_file(file_path)
    payload_dict = payload['result']

    # SciFiReaders reports the wrong units for several Asylum channels (Bias as
    # metres, for one) — patch them before anything downstream reads them.
    for k, ds in payload_dict['datasets'].items():
        ds['units'] = fix_units(ds['title'], ds['units'])

    for ds in payload_dict['datasets'].values():
        a = np.asarray(ds['data'], dtype=np.float32)
        if a.ndim == 2 and min(a.shape) > 1:
            a = np.ascontiguousarray(np.rot90(a, k=ORIENT_K))
        ds['data'] = a
        ds['shape'] = list(a.shape)

    for k in payload_dict['datasets']:
        channels[k] = {kk: payload_dict['datasets'][k][kk] for kk in ch_keys}
        channels[k]['stats'] = get_stats(payload_dict['datasets'][k]['data'])

        preview = save_preview(payload_dict['datasets'][k], dest)
        if preview['ok']:
            channels[k]['preview_path'] = preview['path']
        else:
            print(preview['error'])

        dat = save_array(payload_dict['datasets'][k], dest)
        if dat['ok']:
            channels[k]['array_path'] = dat['path']
        else:
            print(dat['error'])

    arrays = {ds['title']: np.asarray(ds['data'], dtype=np.float32)
              for ds in payload_dict['datasets'].values()}
    measurement_kind = classify_measurement(arrays)

    print(f"[readfile] {measurement_kind}: {len(channels)} channels -> {dest}")

    return {'file_channels': channels, 'kind': measurement_kind}   # type: ignore