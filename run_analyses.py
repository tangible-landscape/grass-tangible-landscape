from grass.exceptions import CalledModuleError, ScriptError
import current_analyses
from utils import get_environment, remove_temp_regions

def run_analyses(output_elev, real_elev, zexag):
    tmp_regions = []
    env = get_environment(tmp_regions, rast=output_elev)
    # run analyses
    functions = [func for func in dir(current_analyses) if func.startswith('run_') and func != 'run_command']
    for func in functions:
        exec('del current_analyses.' + func)
    try:
        reload(current_analyses)
    except:
        pass
    functions = [func for func in dir(current_analyses) if func.startswith('run_') and func != 'run_command']
    for func in functions:
        try:
            exec('current_analyses.' + func + '(real_elev=real_elev, scanned_elev=output_elev, zexag=zexag, env=env)')
        except (CalledModuleError, ScriptError) as e:
            print e
            
    remove_temp_regions(tmp_regions)
