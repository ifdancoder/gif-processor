import cv2
import numpy as np
from PIL import Image
import sys
from tqdm import tqdm

def gif_to_panorama(gif_path, output_path):
    gif = Image.open(gif_path)
    frames = []
    for frame in range(gif.n_frames):
        gif.seek(frame)
        frames.append(np.array(gif.convert("RGB")))

    try:
        print(0)
        stitcher = cv2.Stitcher_create()
        print(1)
        status, panorama = stitcher.stitch(frames)
        print(2)
        if status == cv2.Stitcher_OK:
            cv2.imwrite(output_path, panorama)
            print(f"Панорама сохранена в {output_path}")
        else:
            print("Не удалось автоматически собрать панораму. Пробуем ручной метод.")
            manual_stitch_panorama(frames, output_path)
    except:
        print("OpenCV Stitcher не сработал. Используем ручной метод.")
        manual_stitch_panorama(frames, output_path)


def manual_stitch_panorama(frames, output_path):
    base = frames[0]
    h, w = base.shape[:2]

    canvas = np.zeros((h * 3, w * 3, 3), dtype=np.uint8)
    center_y, center_x = h, w

    canvas[center_y:center_y + h, center_x:center_x + w] = base

    for i in tqdm(range(1, len(frames))):
        frame = frames[i]

        prev_gray = cv2.cvtColor(frames[i - 1], cv2.COLOR_RGB2GRAY)
        curr_gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )

        dx = int(np.mean(flow[..., 0]))
        dy = int(np.mean(flow[..., 1]))

        new_x = center_x + dx
        new_y = center_y + dy

        canvas[new_y:new_y + h, new_x:new_x + w] = frame

        center_x, center_y = new_x, new_y

    gray = cv2.cvtColor(canvas, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    x, y, w, h = cv2.boundingRect(contours[0])

    cropped = canvas[y:y + h, x:x + w]
    cv2.imwrite(output_path, cropped)
    print(f"Панорама (ручной метод) сохранена в {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python gif_to_panorama.py <input.gif> <output.png>")
    else:
        gif_to_panorama(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].split(".")[0] + "_panorama.png")