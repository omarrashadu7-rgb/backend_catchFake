# TODO: Extract image heatmap generation logic here
from pathlib import Path
import shutil


async def generate_heatmap(file_path: str):

    heatmap_dir = Path("uploads/heatmaps")
    heatmap_dir.mkdir(parents=True, exist_ok=True)

    fake_heatmap = heatmap_dir / "sample_heatmap.jpg"

    # copy image as placeholder heatmap
    shutil.copy(file_path, fake_heatmap)

    return str(fake_heatmap)