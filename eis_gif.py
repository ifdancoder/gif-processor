import cv2
import numpy as np
from PIL import Image, ImageSequence
import os
from collections import deque


class GifEISStabilizer:
    def __init__(self, smoothing_radius=15, border_mode='reflect', crop_ratio=0.05):
        """
        EIS для GIF с сохранением качества и FPS

        Args:
            smoothing_radius: радиус сглаживания (меньше = быстрее)
            border_mode: режим границ ('reflect', 'constant', 'wrap')
            crop_ratio: доля обрезки краёв (0-0.2)
        """
        self.smoothing_radius = smoothing_radius
        self.border_mode = border_mode
        self.crop_ratio = crop_ratio

        self.feature_params = dict(
            maxCorners=100,
            qualityLevel=0.05,
            minDistance=20,
            blockSize=7
        )

        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03)
        )

        self.transforms = []
        self.trajectory = []

    def load_gif(self, gif_path):
        """Загрузка GIF с сохранением всех параметров"""
        gif = Image.open(gif_path)

        self.original_duration = gif.info.get('duration', 100)
        self.original_loop = gif.info.get('loop', 0)

        frames = []
        durations = []

        for frame in ImageSequence.Iterator(gif):
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')

            frames.append(np.array(frame))
            durations.append(frame.info.get('duration', self.original_duration))

        return frames, durations

    def detect_and_track(self, prev_gray, curr_gray):
        """Быстрое детектирование и отслеживание"""
        prev_pts = cv2.goodFeaturesToTrack(prev_gray, **self.feature_params)

        if prev_pts is None or len(prev_pts) < 10:
            return np.array([0.0, 0.0, 0.0])

        curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, prev_pts, None, **self.lk_params
        )

        good_prev = prev_pts[status == 1]
        good_curr = curr_pts[status == 1]

        if len(good_prev) < 5:
            return np.array([0.0, 0.0, 0.0])

        transform = cv2.estimateAffinePartial2D(good_prev, good_curr,
                                                method=cv2.RANSAC,
                                                ransacReprojThreshold=3.0)[0]

        if transform is None:
            return np.array([0.0, 0.0, 0.0])

        dx = transform[0, 2]
        dy = transform[1, 2]
        da = np.arctan2(transform[1, 0], transform[0, 0])

        return np.array([dx, dy, da])

    def smooth_trajectory(self, transforms):
        """Быстрое сглаживание траектории"""
        trajectory = np.cumsum(transforms, axis=0)
        smoothed_trajectory = np.zeros_like(trajectory)

        for i in range(len(trajectory)):
            start = max(0, i - self.smoothing_radius // 2)
            end = min(len(trajectory), i + self.smoothing_radius // 2 + 1)
            smoothed_trajectory[i] = np.mean(trajectory[start:end], axis=0)

        correction = smoothed_trajectory - trajectory
        return correction

    def apply_transform(self, frame, correction):
        """Применение коррекции с последующей обрезкой краёв"""
        h, w = frame.shape[:2]
        center = (w // 2, h // 2)

        dx, dy, da = correction

        rotation_matrix = cv2.getRotationMatrix2D(center, np.degrees(da), 1.0)

        rotation_matrix[0, 2] += dx
        rotation_matrix[1, 2] += dy

        if self.border_mode == 'reflect':
            border_mode = cv2.BORDER_REFLECT_101
        elif self.border_mode == 'wrap':
            border_mode = cv2.BORDER_WRAP
        else:
            border_mode = cv2.BORDER_CONSTANT

        stabilized = cv2.warpAffine(frame, rotation_matrix, (w, h),
                                    flags=cv2.INTER_LANCZOS4,
                                    borderMode=border_mode)

        return stabilized

    def crop_frame(self, frame):
        """Обрезка краёв кадра для удаления артефактов"""
        h, w = frame.shape[:2]
        crop_h = int(h * self.crop_ratio)
        crop_w = int(w * self.crop_ratio)

        cropped = frame[crop_h:h - crop_h, crop_w:w - crop_w]

        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)

    def stabilize_gif(self, input_path, output_path):
        """Основная функция стабилизации GIF"""
        print(f"Загрузка GIF: {input_path}")
        frames, durations = self.load_gif(input_path)

        if len(frames) < 2:
            print("Недостаточно кадров для стабилизации")
            return

        print(f"Обработка {len(frames)} кадров...")

        gray_frames = [cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY) for frame in frames]

        transforms = []

        for i in range(1, len(gray_frames)):
            transform = self.detect_and_track(gray_frames[i - 1], gray_frames[i])
            transforms.append(transform)

            if i % 10 == 0:
                print(f"Обработано кадров: {i}/{len(frames)}")

        print("Сглаживание траектории...")
        corrections = self.smooth_trajectory(np.array(transforms))

        # Применяем стабилизацию
        print("Применение стабилизации...")
        stabilized_frames = [frames[0]]

        for i, correction in enumerate(corrections):
            stabilized = self.apply_transform(frames[i + 1], correction)
            stabilized = self.crop_frame(stabilized)
            stabilized_frames.append(stabilized)

        print(f"Сохранение: {output_path}")
        self.save_gif(stabilized_frames, durations, output_path)
        print("Готово!")

    def save_gif(self, frames, durations, output_path):
        """Сохранение GIF с сохранением качества"""
        pil_frames = []

        for frame in frames:
            frame = np.clip(frame, 0, 255).astype(np.uint8)
            pil_frames.append(Image.fromarray(frame))

        pil_frames[0].save(
            output_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=durations,
            loop=self.original_loop,
            optimize=False,  # Отключаем оптимизацию для сохранения качества
            quality=100
        )


def stabilize_gif(input_path, output_path=None, smoothing=15, crop_ratio=0.05):
    """
    Простая функция для стабилизации GIF

    Args:
        input_path: путь к исходному GIF
        output_path: путь к выходному GIF (по умолчанию добавляется '_stabilized')
        smoothing: уровень сглаживания (10-30, больше = плавнее)
        crop_ratio: доля обрезки краёв (0-0.2)
    """
    if output_path is None:
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_stabilized{ext}"

    stabilizer = GifEISStabilizer(smoothing_radius=smoothing, crop_ratio=crop_ratio)
    stabilizer.stabilize_gif(input_path, output_path)
    return output_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование: python eis_gif.py input.gif [output.gif] [smoothing_level] [crop_ratio]")
        print("Пример: python eis_gif.py shaky.gif stable.gif 20 0.05")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    smoothing_level = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    crop_ratio = float(sys.argv[4]) if len(sys.argv) > 4 else 0.05

    if not os.path.exists(input_file):
        print(f"Файл не найден: {input_file}")
        sys.exit(1)

    print("=== EIS Стабилизация GIF ===")
    result = stabilize_gif(input_file, output_file, smoothing_level, crop_ratio)
    print(f"Результат сохранён: {result}")


def batch_stabilize(input_folder, output_folder=None, smoothing=15, crop_ratio=0.05):
    """Пакетная обработка всех GIF в папке"""
    if output_folder is None:
        output_folder = input_folder + "_stabilized"

    os.makedirs(output_folder, exist_ok=True)

    gif_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.gif')]

    for gif_file in gif_files:
        input_path = os.path.join(input_folder, gif_file)
        output_path = os.path.join(output_folder, gif_file)

        print(f"\nОбработка: {gif_file}")
        try:
            stabilize_gif(input_path, output_path, smoothing, crop_ratio)
        except Exception as e:
            print(f"Ошибка при обработке {gif_file}: {e}")

    print(f"\nПакетная обработка завершена. Результаты в: {output_folder}")