"""
Functions to provide Jupyterhub Options forms for our custom spawners.
"""

label_style = "width: 25%"
input_style = "width: 75%"
div_style = "margin-bottom: 16px"
additional_info_style="margin-top: 4px; color: rgb(165,165,165); font-size: 12px;"
optional_label = "<span style=\"font-size: 12px; font-weight: 400;\">(optional)</span>"

def get_options_form(spawner, additional_cpu_info="", additional_memory_info="", additional_gpu_info="") -> str:
    """Return the spawner options screen"""

    # Only show spawner options for named servers (the default server should start with default values)
    if getattr(spawner, "name", "") == "":
        return ''

    description_memory_limit = 'Memory Limit in GB.'
    description_env = 'One name=value pair per line, without quotes'
    description_days_to_live = 'Number of days the container should live'

    default_image = getattr(spawner, "image", "mltooling/ml-workspace:latest")

    # Show / hide custom image input field when checkbox is clicked
    custom_image_listener = "if(event.target.checked){ $('#image-name').css('display', 'block'); $('.defined-images').css('display', 'none'); }else{ $('#image-name').css('display', 'none'); $('.defined-images').css('display', 'block'); }"
    
    # Indicate a wrong input value (not a number) by changing the color to red
    memory_input_listener = "if(isNaN(event.srcElement.value)){ $('#mem-limit').css('color', 'red'); }else{ $('#mem-limit').css('color', 'black'); }"

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
            <label style="{label_style}" for="cpu_limit">CPU Limit {optional_label}</label>
            <input style="{input_style}" name="cpu_limit" placeholder="e.g. 8"></input>
            <div style="{additional_info_style}">{additional_cpu_info}</div>
        </div>
        <div style="{div_style}">
            <label style="{label_style}" for="mem_limit" title="{description_memory_limit}">Memory Limit in GB {optional_label}</label>
            <input style="{input_style}" name="mem_limit" id="mem-limit" title="{description_memory_limit}" placeholder="e.g. 1, 2, 15, ..." oninput="{memory_input_listener}"></input>
            <div style="{additional_info_style}">{additional_memory_info}</div>
        </div>
        <div style="{div_style}">
            <label style="{label_style}" for="env" title="{description_env}">Environment Variables {optional_label}</label>
            <textarea style="{input_style}" name="env" title="{description_env}" placeholder="NAME=VALUE"></textarea>
            <div style="{additional_info_style}">{description_env}</div>
        </div>
        <div style="{div_style}">
            <label style="{label_style}" for="days_to_live" title="{description_days_to_live}">Days to live {optional_label}</label>
            <input style="{input_style}" name="days_to_live" title="{description_days_to_live}" placeholder="e.g. 3"></input>
        </div>
    """.format(
        div_style=div_style,
        label_style=label_style,
        input_style=input_style,
        additional_info_style=additional_info_style,
        default_image=default_image,
        images_template=images_template,
        custom_image_listener=custom_image_listener,
        optional_label=optional_label,
        description_memory_limit=description_memory_limit,
        memory_input_listener=memory_input_listener,
        description_env=description_env,
        description_days_to_live=description_days_to_live,
        additional_cpu_info=additional_cpu_info,
        additional_memory_info=additional_memory_info,
    )

def get_options_form_docker(spawner):
    description_gpus = 'Leave empty for no GPU, "all" for all GPUs, or a comma-separated list of indices of the GPUs (e.g 0,2).'
    additional_info = {
        "additional_cpu_info": "Host has {cpu_count} CPUs".format(cpu_count=spawner.resource_information['cpu_count']),
        "additional_memory_info": "Host has {memory_count_in_gb}GB memory".format(memory_count_in_gb=spawner.resource_information['memory_count_in_gb']),
        "additional_gpu_info": "<div>Host has {gpu_count} GPUs</div><div>{description_gpus}</div>".format(gpu_count=spawner.resource_information['gpu_count'], description_gpus=description_gpus)
    }
    options_form = get_options_form(spawner, **additional_info)
    
    # When GPus shall be used, change the default image to the default gpu image (if the user entered a different image, it is not changed), and show an info box
    # reminding the user of inserting a GPU-leveraging docker image
    show_gpu_info_box = "$('#gpu-info-box').css('display', 'block');"
    hide_gpu_info_box = "$('#gpu-info-box').css('display', 'none');"
    gpu_input_listener = "if(event.srcElement.value !== ''){{ {show_gpu_info_box} }}else{{ {hide_gpu_info_box} }}" \
        .format(
            show_gpu_info_box=show_gpu_info_box, 
            hide_gpu_info_box=hide_gpu_info_box
    )

    gpu_disabled = ""
    if spawner.resource_information['gpu_count'] < 1:
        gpu_disabled = "disabled"

    additional_shm_size_info = "This will override the default shm_size value. Check the <a href='https://docs.docker.com/compose/compose-file/#shm_size'>documentation</a> for more info."
    options_form_docker = \
    """
    <div style="{div_style}">
        <label style="{label_style}" for="shm_size">Shared Memory Size {optional_label}</label>
        <input style="{input_style}" name="shm_size" placeholder="default is {default_shm_size}"></input>
        <div style="{additional_info_style}">{additional_shm_size_info}</div>
    </div>
    <div style="{div_style}">
        <input style="margin-right: 8px;" type="checkbox" name="is_mount_volume" checked></input>
        <label style="font-weight: 400;" for="is_mount_volume">Mount named volume to /workspace?</label>
    </div>
    <div style="{div_style}">
        <label style="{label_style}" for="gpus" title="{description_gpus}">GPUs {optional_label}</label>
        <input style="{input_style}" name="gpus" title="{description_gpus}" placeholder="e.g. all, 0, 1, 2, ..." oninput="{gpu_input_listener} {gpu_disabled}"></input>
        <div style="{additional_info_style}">{additional_gpu_info}</div>
        <div style="background-color: #ffa000; padding: 8px; margin-top: 4px; display: none; {input_style}" id="gpu-info-box">When using GPUs, make sure to use a GPU-supporting Docker image!</div>
    </div>
    """.format(
        div_style=div_style,
        label_style=label_style,
        input_style=input_style,
        additional_info_style=additional_info_style,
        optional_label=optional_label,
        default_shm_size=spawner.extra_host_config["shm_size"] if "shm_size" in spawner.extra_host_config else "0m",
        additional_shm_size_info=additional_shm_size_info,
        gpu_input_listener=gpu_input_listener,
        gpu_disabled=gpu_disabled,
        description_gpus=description_gpus,
        additional_gpu_info=additional_info['additional_gpu_info']
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

    options['shm_size'] = formdata.get('shm_size', [None])[0]
    options['gpus'] = formdata.get('gpus', [None])[0]

    return options
