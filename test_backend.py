"""
Backend Integration Test — Image & Video Prediction
Run from the backend_fastapi directory:
    python test_backend.py
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, ".")


async def main():
    from app.services.image_service.predictor import predict_image
    from app.services.video_service.predictor import predict_video
    import httpx

    print("=" * 60)
    print("BACKEND TEST: IMAGE + VIDEO PREDICTION")
    print("=" * 60)

    tmp_dir = tempfile.gettempdir()

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        # Download test image
        img_resp = await client.get(
            "https://raw.githubusercontent.com/gradio-app/gradio/main/test/test_files/bus.png"
        )
        img_path = os.path.join(tmp_dir, "test_image.png")
        with open(img_path, "wb") as f:
            f.write(img_resp.content)
        print(f"Test image : {len(img_resp.content)} bytes -> {img_path}")

        # Download test video
        vid_resp = await client.get("https://www.w3schools.com/html/mov_bbb.mp4")
        vid_path = os.path.join(tmp_dir, "test_video.mp4")
        with open(vid_path, "wb") as f:
            f.write(vid_resp.content)
        print(f"Test video : {len(vid_resp.content)} bytes -> {vid_path}")

    # -- TEST IMAGE ------------------------------------------------
    print()
    print(">>> Testing IMAGE prediction...")
    try:
        img_result = await predict_image(img_path)
        print("[IMAGE] SUCCESS!")
        print("  prediction   :", img_result["prediction"])
        print("  confidence   :", img_result["confidence"])
        print("  process_time :", img_result["processing_time"], "s")
        heatmap = str(img_result.get("heatmap_url") or "")
        print("  heatmap_url  :", heatmap[:80] + "..." if len(heatmap) > 80 else heatmap)
    except Exception as e:
        print("[IMAGE] FAILED:", e)

    # -- TEST VIDEO ------------------------------------------------
    print()
    print(">>> Testing VIDEO prediction...")
    try:
        vid_result = await predict_video(vid_path)
        print("[VIDEO] SUCCESS!")
        print("  prediction   :", vid_result["prediction"])
        print("  confidence   :", vid_result["confidence"])
        print("  fake_prob    :", vid_result["fake_probability"])
        print("  source       :", vid_result["result_source"])
    except Exception as e:
        print("[VIDEO] FAILED:", e)

    print()
    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
