import os
import shutil
import tarfile
import zipfile
import mimetypes
from PIL import Image
from typing import List
from cog import BasePredictor, Input, Path
from comfyui import ComfyUI
import json

OUTPUT_DIR = "/tmp/outputs"
INPUT_DIR = "/tmp/inputs"
COMFYUI_TEMP_OUTPUT_DIR = "ComfyUI/temp"

mimetypes.add_type("image/webp", ".webp")

with open("examples/api_workflows/avatar_30may.json", "r") as file:
    EXAMPLE_WORKFLOW_JSON = file.read()


class Predictor(BasePredictor):
    def setup(self):
        self.comfyUI = ComfyUI("127.0.0.1:8188")
        self.comfyUI.start_server(OUTPUT_DIR, INPUT_DIR)

    def cleanup(self):
        self.comfyUI.clear_queue()
        for directory in [OUTPUT_DIR, INPUT_DIR, COMFYUI_TEMP_OUTPUT_DIR]:
            if os.path.exists(directory):
                shutil.rmtree(directory)
            os.makedirs(directory)

    def handle_input_file(self, input_file: Path):
        file_extension = os.path.splitext(input_file)[1].lower()
        if file_extension in [".jpg", ".jpeg", ".png", ".webp"]:
            filename = f"input{file_extension}"
            shutil.copy(input_file, os.path.join(INPUT_DIR, filename))
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        return filename

    def update_workflow(self, workflow, **kwargs):
        load_image = workflow["50"]["inputs"]
        load_image["image"] = kwargs["filename"]
        prompt = workflow["9"]["inputs"]["text"] = f"{kwargs['prompt']}"
        neg_prompt = workflow["10"]["inputs"]["text"]= f"{kwargs['negative_prompt']}"





    def log_and_collect_files(self, directory, prefix=""):
        files = []
        for f in os.listdir(directory):
            if f == "__MACOSX":
                continue
            path = os.path.join(directory, f)
            if os.path.isfile(path):
                print(f"{prefix}{f}")
                files.append(Path(path))
            elif os.path.isdir(path):
                print(f"{prefix}{f}/")
                files.extend(self.log_and_collect_files(path, prefix=f"{prefix}{f}/"))
        return files

    def predict(
        self,
        image: Path = Input(
            description="An image of a person to be converted to a sticker",
            default=None,
        ),
        prompt: str = Input(
            description="Prompt to generate the sticker",
            default="photo of a cheerful boy sitting, realistic, 4k 8k photograph, studio photography, sharp, blue pyjamas",
        ),
        negative_prompt: str = Input(
            description="Negative prompt to generate the sticker",
            default="text, watermark, unsharp, blurry, render, bad anatomy, weird, strange",
        ),        
        return_temp_files: bool = Input(
            description="Return any temporary files, such as preprocessed controlnet images. Useful for debugging.",
            default=False,
        ),
        output_format: str = Input(
            description="Format of the output images",
            choices=["webp", "jpg", "png"],
            default="webp",
        ),
        output_quality: int = Input(
            description="Quality of the output images, from 0 to 100. 100 is best quality, 0 is lowest quality.",
            default=80,
            ge=0,
            le=100,
        ),
        randomise_seeds: bool = Input(
            description="Automatically randomise seeds (seed, noise_seed, rand_seed)",
            default=True,
        ),
        force_reset_cache: bool = Input(
            description="Force reset the ComfyUI cache before running the workflow. Useful for debugging.",
            default=False,
        ),
    ) -> List[Path]:
        """Run a single prediction on the model"""
        self.cleanup()


        workflow = json.loads(EXAMPLE_WORKFLOW_JSON)

        if image is None:
            raise ValueError("No image provided")
        filename = self.handle_input_file(image)
        self.update_workflow(
            workflow,
            filename=filename,
            prompt=prompt,
            negative_prompt=negative_prompt,
        )
        wf = self.comfyUI.load_workflow(workflow)



        self.comfyUI.connect()

        if force_reset_cache or not randomise_seeds:
            self.comfyUI.reset_execution_cache()

        if randomise_seeds:
            self.comfyUI.randomise_seeds(wf)

        self.comfyUI.run_workflow(wf)

        files = []
        output_directories = [OUTPUT_DIR]
        if return_temp_files:
            output_directories.append(COMFYUI_TEMP_OUTPUT_DIR)

        for directory in output_directories:
            print(f"Contents of {directory}:")
            files.extend(self.log_and_collect_files(directory))

        if output_quality < 100 or output_format in ["webp", "jpg"]:
            optimised_files = []
            for file in files:
                if file.is_file() and file.suffix in [".jpg", ".jpeg", ".png"]:
                    image = Image.open(file)
                    optimised_file_path = file.with_suffix(f".{output_format}")
                    image.save(
                        optimised_file_path,
                        quality=output_quality,
                        optimize=True,
                    )
                    optimised_files.append(optimised_file_path)
                else:
                    optimised_files.append(file)

            files = optimised_files

        return files
