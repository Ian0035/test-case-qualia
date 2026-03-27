from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qualia_lerobot_augmentor.video import _build_ffmpeg_command


class VideoTests(unittest.TestCase):
    def test_build_ffmpeg_command_uses_browser_playable_h264_settings(self) -> None:
        command = _build_ffmpeg_command(
            ffmpeg_exe="ffmpeg",
            temp_path=Path("out.mp4"),
            fps=29.97,
            width=640,
            height=480,
        )

        self.assertIn("libx264", command)
        self.assertIn("yuv420p", command)
        self.assertIn("bgr24", command)
        self.assertEqual(command[-1], "out.mp4")


if __name__ == "__main__":
    unittest.main()
