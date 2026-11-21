from games.tango_solver.src.tango_solver import TangoSolver


def test_animation_is_an_injected_output_port() -> None:
    class Recorder:
        def __init__(self):
            self.frames = []
            self.output = None

        def save_frame(self, *args):
            self.frames.append(args[-1])

        def create_gif(self, **kwargs):
            self.output = kwargs
            return kwargs["output_path"]

    recorder = Recorder()
    solver = TangoSolver(visualizer=recorder)
    assert solver.solve(create_gif=True, gif_output="example.gif")
    assert recorder.frames[-1].endswith("SOLVED")
    assert recorder.output["output_path"] == "example.gif"
