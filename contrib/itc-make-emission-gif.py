import imageio.v2 as imageio
import os

frames_dir = "gif_frames"
output_gif = "itc_emission_curve.gif"

filenames = sorted([
    os.path.join(frames_dir, f)
    for f in os.listdir(frames_dir)
    if f.endswith(".png")
])

print(f"🧵 Compiling {len(filenames)} frames into {output_gif}...")

with imageio.get_writer(output_gif, mode='I', fps=20) as writer:
    for i, filename in enumerate(filenames):
        image = imageio.imread(filename)
        writer.append_data(image)
        if i % 25 == 0:
            print(f"  ➤ Added frame {i}/{len(filenames)}")

print(f"✅ GIF saved: {output_gif}")
