from PIL import Image
import sys


def gif_to_full_frame(gif_path, output_path):
    try:
        gif = Image.open(gif_path)

        base = gif.convert("RGBA")
        gif.seek(0)

        for frame in range(1, gif.n_frames):
            gif.seek(frame)
            frame_img = gif.convert("RGBA")
            base = Image.alpha_composite(base, frame_img)

        base.save(output_path, format="PNG")
        print(f"Полный кадр сохранен в {output_path}")

    except Exception as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python gif_to_fullframe.py <input.gif> <output.png>")
    else:
        gif_to_full_frame(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].split(".")[0] + "_full_frame.png")