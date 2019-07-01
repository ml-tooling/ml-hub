from dockerspawner import DockerSpawner

from traitlets import (default)
from tornado import gen
import multiprocessing

class MLHubDockerSpawner(DockerSpawner):
    """Provides the possibility to spawn docker containers with specific options, such as resource limits (CPU and Memory), Environment Variables, ..."""

    @default('options_form')
    def _options_form(self):
        """Return the spawner options screen"""

        # Only show spawner options for named servers (the default server should start with default values)
        if getattr(self, "name", "") == "":
            return ''

        description_memory_limit = 'Minimum limit must be 4mb as required by Docker.'
        description_env = 'In the form env=value (one per line)'
        description_gpus = 'Empty for no GPU-acess. A comma-separted list of numbers describe the indices of the accessible GPUs.'
        # template = super()._default_options_form()
        return """
            <label for="image">Docker Image</label>
            <input name="image" placeholder="e.g. mltooling/ml-workspace"></input>
            <br />
            <label for="cpu_limit">Number of CPUs</label>
            <input name="cpu_limit" placeholder="e.g. 8"></input>
            <br />
            <label for="mem_limit" title="{description_memory_limit}">Memory Limit</label>
            <input name="mem_limit" title="{description_memory_limit}" placeholder="e.g. 100mb, 8g, ..."></input>
            <br />
            <label for="env" title="{description_env}">Environment Variables</label>
            <textarea name="env" title="{description_env}"></textarea>
            <br />
            <input type="checkbox" name="mount_volume" title="Mount a named volume to /workspace">Mount a volume</input> 
            <br />
            <label for="gpus" title="{description_gpus}">GPUs</label>
            <input name="gpus" title="{description_gpus}" placeholder="e.g. all, 0, 1, 2, ..."></input>
        """.format(
            description_memory_limit=description_memory_limit,
            description_env=description_env,
            description_gpus=description_gpus
        )

    def options_from_form(self, formdata):
        """Extract the passed form data into the self.user_options variable."""

        options = {}

        options["image"] = formdata.get('image', [None])[0]
        options["cpu_limit"] = formdata.get('cpu_limit', [None])[0]
        options["mem_limit"] = formdata.get('mem_limit', [None])[0]
        options["mount_volume"] = formdata.get('mount_volume', [False])[0]

        env = {}
        env_lines = formdata.get('env', [''])
        print(formdata)
        print(env_lines)
        print(env_lines[0])
        for line in env_lines[0].splitlines():
            if line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
        options['env'] = env

        options['gpus'] = formdata.get('gpus', [None])[0]

        return options

    def get_env(self):
        env = super().get_env()
        if self.user_options.get('env'):
            env.update(self.user_options.get('env'))

        if self.user_options.get('gpus'):
            env['NVIDIA_VISIBLE_DEVICES'] = self.user_options.get('gpus')
            env['CUDA_VISIBLE_DEVICES'] = self.user_options.get('gpus')

        if self.user_options.get('cpu_limit'):
            env["OMP_NUM_THREADS"] = self.user_options.get('cpu_limit')

        return env

    @gen.coroutine
    def start(self):

        if self.user_options.get('image'):
            self.image = self.user_options.get('image')

        extra_host_config = {}
        if self.user_options.get('cpu_limit'):
            # nano_cpus cannot be bigger than the number of CPUs of the machine (this method would currently not work in a cluster, as machines could be different than the machine where the runtime-manager and this code run.
            max_available_cpus = multiprocessing.cpu_count()
            limited_cpus = min(int(self.user_options.get('cpu_limit')), max_available_cpus)

            # the nano_cpu parameter of the Docker client expects an integer, not a float
            nano_cpus = int(limited_cpus * 1e9)
            extra_host_config['nano_cpus'] = nano_cpus
        if self.user_options.get('mem_limit'):
            extra_host_config['mem_limit'] = self.user_options.get(
                'mem_limit')
        
        if self.user_options.get('mount_volume') == 'on':
            server_name = getattr(self, "name", "")
            self.volumes = { 'jupyterhub-user-{username}' + server_name: "/workspace" }

        if self.user_options.get('gpus'):
            extra_host_config['runtime'] = "nvidia"

        self.extra_host_config.update(extra_host_config)

        res = yield super().start()
        return res
