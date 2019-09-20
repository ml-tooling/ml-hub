"""
Functions to provide Jupyterhub Options forms for our custom spawners.
"""

label_style = "width: 25%"
input_style = "width: 75%"
div_style = "margin-bottom: 16px"
optional_label = "<span style=\"font-size: 12px; font-weight: 400;\">(optional)</span>"

def get_options_form(spawner):
    """Return the spawner options screen"""

    # Only show spawner options for named servers (the default server should start with default values)
    if getattr(spawner, "name", "") == "":
        return ''

    description_memory_limit = 'Minimum limit must be 4mb as required by Docker.'
    description_env = 'In the form env=value (one per line)'
    description_days_to_live = 'Number of days the container should live'

    default_image = getattr(spawner, "image", "mltooling/ml-workspace:latest")

    # Show / hide custom image input field when checkbox is clicked
    custom_image_listener = "if(event.target.checked){ $('#image-name').css('display', 'block'); $('.defined-images').css('display', 'none'); }else{ $('#image-name').css('display', 'none'); $('.defined-images').css('display', 'block'); }"

    # Create drop down menu with pre-defined custom images
    image_option_template = """
        <option value="{image}">{image}</option>
    """
    image_options = ""
    for image in spawner.workspace_images:
        image_options += image_option_template.format(image=image)

    images_template = """
        <select name="defined_image" class="defined-images" required autofocus>{image_options}</select>
    """.format(image_options=image_options)

    # template = super()._default_options_form()
    return """
        <div style="{div_style}">
            <label style="{label_style}" for="image">Docker Image</label>
            <div name="image">
                <div style="margin-bottom: 4px">
                    <input style="margin-right: 8px;" type="checkbox" name="is_custom_image" onchange="{custom_image_listener}"></input>
                    <label style="font-weight: 400;" for="is_custom_image">Custom Image</label>
                </div>
                <input style="{input_style}; display: none;" name="custom_image" id="image-name" class="custom-image" placeholder="Custom Image"></input>
                {images_template}
            </div>
        </div>
        <div style="{div_style}">
            <label style="{label_style}" for="cpu_limit">Number of CPUs {optional_label}</label>
            <input style="{input_style}" name="cpu_limit" placeholder="e.g. 8"></input>
        </div>
        <div style="{div_style}">
            <label style="{label_style}" for="mem_limit" title="{description_memory_limit}">Memory Limit {optional_label}</label>
            <input style="{input_style}" name="mem_limit" title="{description_memory_limit}" placeholder="e.g. 100mb, 8g, ..."></input>
        </div>
        <div style="{div_style}">
            <label style="{label_style}" for="env" title="{description_env}">Environment Variables {optional_label}</label>
            <textarea style="{input_style}" name="env" title="{description_env}" placeholder="FOO=BAR&#10;FOO2=BAR2"></textarea>
        </div>
        
        <div style="{div_style}">
            <label style="{label_style}" for="days_to_live" title="{description_days_to_live}">Days to live {optional_label}</label>
            <input style="{input_style}" name="days_to_live" title="{description_days_to_live}" placeholder="e.g. 3"></input>
        </div>
    """.format(
        div_style=div_style,
        label_style=label_style,
        input_style=input_style,
        default_image=default_image,
        images_template=images_template,
        custom_image_listener=custom_image_listener,
        optional_label=optional_label,
        description_memory_limit=description_memory_limit,
        description_env=description_env,
        description_days_to_live=description_days_to_live
    )

def get_options_form_docker(spawner):
    options_form = get_options_form(spawner)


    # When GPus shall be used, change the default image to the default gpu image (if the user entered a different image, it is not changed), and show an info box
    # reminding the user of inserting a GPU-leveraging docker image
    show_gpu_info_box = "$('#gpu-info-box').css('display', 'block');"
    hide_gpu_info_box = "$('#gpu-info-box').css('display', 'none');"
    description_gpus = 'Empty for no GPU-acess. A comma-separted list of numbers describe the indices of the accessible GPUs.'
    gpu_input_listener = "if(event.srcElement.value !== ''){{ {show_gpu_info_box} }}else{{ {hide_gpu_info_box} }}" \
        .format(
            show_gpu_info_box=show_gpu_info_box, 
            hide_gpu_info_box=hide_gpu_info_box
    )

    options_form_docker = \
    """
    <div style="{div_style}">
        <input style="margin-right: 8px;" type="checkbox" name="is_mount_volume" checked></input>
        <label style="font-weight: 400;" for="is_mount_volume">Mount named volume to /workspace?</label>
    </div>
    <div style="{div_style}">
        <label style="{label_style}" for="gpus" title="{description_gpus}">GPUs {optional_label}</label>
        <input style="{input_style}" name="gpus" title="{description_gpus}" placeholder="e.g. all, 0, 1, 2, ..." oninput="{gpu_input_listener}"></input>
        <div style="background-color: #ffa000; padding: 8px; margin-top: 4px; display: none; {input_style}" id="gpu-info-box">When using GPUs, make sure to use a GPU-supporting Docker image!</div>
    </div>
    """.format(
        div_style=div_style,
        label_style=label_style,
        input_style=input_style,
        optional_label=optional_label,
        gpu_input_listener=gpu_input_listener,
        description_gpus=description_gpus
    )

    return options_form + options_form_docker

def options_from_form(spawner, formdata):
    """Extract the passed form data into the self.user_options variable."""
    options = {}

    if formdata.get('is_custom_image', ["off"])[0] == "on":
        options["image"] = formdata.get('custom_image', [None])[0]
    else:
        options["image"] = formdata.get('defined_image', [None])[0]

    options["cpu_limit"] = formdata.get('cpu_limit', [None])[0]
    options["mem_limit"] = formdata.get('mem_limit', [None])[0]
    options["is_mount_volume"] = formdata.get('is_mount_volume', ["off"])[0]
    options["days_to_live"] = formdata.get('days_to_live', [None])[0]

    env = {}
    env_lines = formdata.get('env', [''])

    for line in env_lines[0].splitlines():
        if line:
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    options['env'] = env

    options['gpus'] = formdata.get('gpus', [None])[0]

    return options
