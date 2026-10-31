import argparse
import json
import sys
from src.config import ConfigError, SimConfig
from src.sim.controller import SimulationController
from src.sim.simulation import Simulation
from src.render.save_frame import save_frame
from src.render.tk_app import launch


SHORTCUTS = {"seed": "simulation.seed", "duration": "simulation.duration", "dt": "simulation.dt",
    "drivers": "drivers.num_drivers", "width": "city.width", "height": "city.height",
    "houses": "city.num_houses", "rate": "requests.rate", "request_generator": "requests.generator",
    "router": "routing.strategy", "dispatcher": "dispatch.strategy",
    "light_phase": "traffic.light_phase_duration", "vehicle_speed": "traffic.vehicle_speed",
    "speed": "render.speed"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="main.py", description="City delivery simulator")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--headless", action="store_true", help="run without a window, print metrics")
    mode.add_argument("--render", action="store_true", help="open the window (default)")
    p.add_argument("--config", metavar="FILE", help="JSON config file")
    p.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE",
                   help="override any option, e.g. --set traffic.all_red_time=0 (repeatable)")
    p.add_argument("--seed", type=int, help="random seed")
    p.add_argument("--duration", type=float, help="simulated seconds to run")
    p.add_argument("--dt", type=float, help="seconds per timestep")
    p.add_argument("--drivers", type=int, help="number of drivers")
    p.add_argument("--width", type=int, help="city width in intersections")
    p.add_argument("--height", type=int, help="city height in intersections")
    p.add_argument("--houses", type=int, help="number of houses")
    p.add_argument("--rate", type=float, help="requests per simulated second")
    p.add_argument("--request-generator", dest="request_generator", help="request generator name")
    p.add_argument("--router", help="routing strategy name")
    p.add_argument("--dispatcher", help="dispatch strategy name")
    p.add_argument("--light-phase", dest="light_phase", type=float, help="green seconds per phase")
    p.add_argument("--vehicle-speed", dest="vehicle_speed", type=float, help="car speed in m/s")
    p.add_argument("--speed", type=float, help="renderer speed: simulated seconds per real second")
    p.add_argument("--no-autostart", action="store_true", help="renderer: start paused")
    p.add_argument("--metrics-out", metavar="FILE", help="write the final metrics summary as JSON")
    p.add_argument("--save-frame", metavar="PNG", help="after running, save a picture of the final state (needs Pillow)")
    p.add_argument("--print-config", action="store_true", help="print the resolved config and exit")
    p.add_argument("--quiet", action="store_true", help="headless: no progress output")
    return p


def config_from_args(args: argparse.Namespace) -> SimConfig:
    cfg = SimConfig.load(args.config) if args.config else SimConfig()
    overrides = {SHORTCUTS[k]: getattr(args, k) for k in SHORTCUTS if getattr(args, k, None) is not None}
    cfg = cfg.with_overrides(overrides) if overrides else cfg
    return cfg.with_overrides(args.overrides) if args.overrides else cfg


def format_summary(summary: dict) -> str:
    def f(v, spec=".1f"):
        return "n/a" if v is None else format(v, spec)

    return "\n".join([f"simulated time        {summary['time']:.0f} s ({summary['tick']} ticks)",
        f"requests              created {summary['requests_created']}, completed "
        f"{summary['requests_completed']}, still active {summary['requests_active']}",
        f"drivers               available {summary['drivers_available']}, busy {summary['drivers_busy']}"
        f"  (utilisation {summary['driver_utilisation'] * 100:.0f}%)",
        f"delivery time (avg)   {f(summary['avg_completion_time'])} s   "
        f"[wait {f(summary['avg_wait_time'])} + to pickup {f(summary['avg_pickup_time'])} "
        f"+ transit {f(summary['avg_transit_time'])}]",
        f"driving time (total)  {summary['total_travel_time_s']:.0f} s moving, "
        f"{summary['total_stopped_time_s']:.0f} s stopped",
        f"distance (total)      {summary['total_distance_m'] / 1000:.2f} km "
        f"({summary['avg_distance_per_driver_m'] / 1000:.2f} km per driver)"])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = config_from_args(args)
    except (ConfigError, OSError, json.JSONDecodeError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    if args.print_config:
        print(json.dumps(cfg.to_dict(), indent=2))
        return 0

    try:
        sim = Simulation(cfg)
    except (ConfigError, KeyError) as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    controller = SimulationController(sim)

    headless = args.headless or (not args.render and not cfg.render.enabled)
    if headless:
        def progress(s: Simulation) -> None:
            if not args.quiet:
                m = s.metrics.current(s)
                print(f"  t={m['time']:7.0f}s  completed={m['requests_completed']:4d}  "
                      f"active={m['requests_active']:3d}  busy={m['drivers_busy']:3d}", file=sys.stderr)

        controller.run(progress=progress, progress_every=300.0)
    else:
        try:
            launch(controller, autostart=not args.no_autostart)
        except ImportError as exc:      # tkinter missing (some minimal Python installs)
            print(f"Cannot open the renderer ({exc}). Install Tk support or use --headless.",
                  file=sys.stderr)
            return 1

    summary = sim.metrics.summary(sim)
    if headless or sim.clock.tick:
        print(format_summary(summary))
    if args.metrics_out:
        with open(args.metrics_out, "w", encoding="utf-8") as fh:
            json.dump({"config": cfg.to_dict(), "summary": summary,
                       "deliveries": [d.to_dict() for d in sim.metrics.deliveries],
                       "samples": sim.metrics.samples}, fh, indent=2)
    if args.save_frame:
        save_frame(sim, args.save_frame)
        print(f"saved {args.save_frame}")
    return 0

main()