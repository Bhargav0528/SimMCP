# Python interface to MATLAB UAV scenario functions via MATLAB Engine API

import matlab.engine
import numpy as np
import ast


class MATLABSession:
    def __init__(self):
        self.eng = matlab.engine.start_matlab(
            "-nosplash")
        self.eng.desktop(nargout=0)

    def close(self):
        self.eng.quit()


_SESS: dict[str, MATLABSession] = {}


def _create_session() -> str:
    sid = 0
    _SESS[sid] = MATLABSession()
    return sid


def _get(sid: str) -> MATLABSession:
    if sid not in _SESS:
        raise ValueError("invalid session id")
    return _SESS[sid]


def start_matlab_engine():
    """Starts a MATLAB engine session."""
    return _create_session()


def create_uav_scenario(reference_location, update_rate):
    """
    Create a uavScenario in MATLAB and store it in the workspace.
    Args:
        reference_location: List of [lat, lon, alt].
        update_rate: Scenario update rate in Hz.
    Side Effects:
        Creates a MATLAB workspace variable named 'scene' containing the uavScenario object.
    """
    eng = _get(0).eng
    reference_location = ast.literal_eval(reference_location)
    reference_location = np.array(reference_location)
    eng.workspace['refLoc'] = matlab.double(reference_location)
    eng.workspace['updateRate'] = float(update_rate)
    eng.eval(
        "scene = uavScenario(ReferenceLocation=refLoc, UpdateRate=updateRate);", nargout=0)


def add_mesh(mesh_type, name, color, xLimits=[-200, 200], yLimits=[-150, 150]):
    """
    Adds a mesh (terrain or buildings) to the scene.
    Args:
        mesh_type: 'terrain' or 'buildings'.
        name: it can either be terrainName or OSMFileName based on the mesh_type
        xLimits: xLimits for the terrain
        yLimits: yLimits for the terrain
        color: RGB list.
    """
    eng = _get(0).eng

    if (mesh_type == "terrain"):
        geom_cell = eng.cell(1, 3)
        geom_cell[0] = name

        geom_cell[1] = matlab.double(xLimits)

        geom_cell[2] = matlab.double(yLimits)

        color = [0.6, 0.6, 0.6]
    elif (mesh_type == "buildings"):
        geom_cell = eng.cell(1, 4)
        geom_cell[0] = name

        geom_cell[1] = matlab.double(xLimits)

        geom_cell[2] = matlab.double(yLimits)

        geom_cell[3] = "auto"

        color = [0.6431, 0.8706, 0.6275]

    eng.workspace['geom'] = geom_cell
    eng.eval(
        "addMesh(scene" + f", \"{mesh_type}\", geom, {color});", nargout=0)


def create_platform(name="UAV"):
    """
    Creates a UAV platform in the scenario and stores it in the workspace.
    Args:
        name: UAV name.
    Side Effects:
        Creates a MATLAB workspace variable named 'platform' containing the uavPlatform object.
    """
    eng = _get(0).eng
    scene = _get(0).eng.workspace['scene']
    eng.eval(f"platform = uavPlatform('{name}', {scene});", nargout=0)


def update_platform_mesh(mesh_type, size_param, color, transform_matrix):
    """
    Updates the UAV mesh.
    Args:
        mesh_type: 'quadrotor' or 'custom'.
        size_param: [scale] or [dims].
        color: RGB list.
        transform_matrix: 4x4 transform matrix.
    """
    eng = _get(0).eng
    eng.workspace['sizeParam'] = matlab.cell2mat(matlab.double(size_param))
    eng.workspace['color'] = matlab.double(color)
    eng.workspace['T'] = matlab.double(transform_matrix)
    eng.eval(
        f"updateMesh(platform, '{mesh_type}', {{sizeParam}}, color, T);", nargout=0)


def load_uav_mission(plan_file):
    """
    Loads a UAV mission plan and stores it in the workspace.
    Args:
        plan_file: .plan file path.
    Side Effects:
        Creates a MATLAB workspace variable named 'mission' containing the uavMission object.
    """
    eng = _get(0).eng
    eng.workspace['planFile'] = plan_file
    eng.eval("mission = uavMission(PlanFile=planFile);", nargout=0)


def create_mission_parser():
    """
    Creates a multirotor mission parser and stores it in the workspace.
    Side Effects:
        Creates a MATLAB workspace variable named 'parser' containing the multirotorMissionParser object.
    """
    eng = _get(0).eng
    eng.eval("parser = multirotorMissionParser;", nargout=0)


def parse_mission():
    """
    Parses a mission into a trajectory object and stores it in the workspace. Takes the reference location value from scene
    Side Effects:
        Creates a MATLAB workspace variable named 'trajectory'.
    """
    eng = _get(0).eng
    eng.eval(
        f"trajectory = parse(parser, mission, scene.ReferenceLocation);", nargout=0)


def show_3d_scene():
    """
    Shows 3D visualization of the scene and stores the axes handle.
    Side Effects:
        Creates a MATLAB workspace variable named 'ax' containing the handle to the plot axes.
    """
    eng = _get(0).eng
    eng.eval(f"ax = show3D(scene);", nargout=0)


def setup_scenario():
    """Prepares scenario for simulation."""
    eng = _get(0).eng
    scene = _get(0).eng.workspace['scene']
    eng.eval(f"setup({scene});", nargout=0)


def advance_scenario():
    """
    Advances the simulation by one step and stores the completion status.
    Side Effects:
        Creates or updates a MATLAB workspace variable named 'isDone' with the simulation status.
    """
    eng = _get(0).eng
    eng.eval(f"isDone = advance(scene);", nargout=0)


def query_trajectory(time):
    """
    Queries the trajectory at a specific time and stores the result.
    Args:
        time: The time at which to query the trajectory.
    Side Effects:
        Creates a MATLAB workspace variable named 'motionInfo' containing the position and orientation.
    """
    eng = _get(0).eng
    eng.workspace['t'] = float(time)
    eng.eval(f"motionInfo = query(trajectory, t);", nargout=0)


def move_platform(plat, motion_vector):
    """Moves the UAV platform."""
    eng = _get(0).eng
    eng.eval(f"move(platform, motionInfo);", nargout=0)


def update_camera_target(ax, ned_position):
    """Sets the camera target."""
    eng = _get(0).eng
    target = [ned_position[1], ned_position[0], -ned_position[2]]
    eng.workspace['target'] = matlab.double(target)
    eng.eval(f"camtarget({ax}, target);", nargout=0)


def drawnow_limitrate():
    """Forces MATLAB graphics to update."""
    eng = _get(0).eng
    eng.eval("drawnow limitrate;", nargout=0)
