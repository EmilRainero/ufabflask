import json

def json_file_to_dict(file_path):
    with open(file_path) as jf1:
        json_string = jf1.read()
        return json.loads(json_string)

def process_milling_tool(tool):
    print('{0},{1},{2},{3}'.format(
          tool['toolType'],
          tool['diameter'],
          tool['depthMax'],
          tool['cuttingData']['Results']['MillingResultElement']['Qq']
          ))

def process_milling_tools(milling_tools):
    print('Milling tools:', len(milling_tools))
    print('{0},{1},{2},{3}'.format('Type', 'Diameter', 'DepthMax', 'Qq'))
    for milling_tool in milling_tools:
        process_milling_tool(milling_tool)

def process_finishing_tool(tool):
    results = tool['cuttingData']['Results']
    milling_results = results['MillingResultElement']
    finishing_side_Qq = ''
    finishing_bottom_Qq = ''
    premachining_side_Qq = ''
    premachining_bottom_Qq = ''
    if isinstance(milling_results, list):
        for entry in milling_results:
            if entry['StrategyStep'] == 'FinishingSide':
                finishing_side_Qq = entry['Qq']
            if entry['StrategyStep'] == 'FinishingBottom':
                finishing_bottom_Qq = entry['Qq']
            if entry['StrategyStep'] == 'PremachiningSide':
                premachining_side_Qq = entry['Qq']
            if entry['StrategyStep'] == 'PremachiningBottom':
                premachining_bottom_Qq = entry['Qq']
    else:
        finishing_side_Qq = milling_results['Qq']
        finishing_bottom_Qq = milling_results['Qq']

    print('{0},{1},{2},{3},{4},{5},{6}'.format(
        tool['call'],
        tool['diameter'],
        tool['depthMax'],
        finishing_side_Qq,
        finishing_bottom_Qq,
        premachining_side_Qq,
        premachining_bottom_Qq
    ))

def process_finishing_tools(finishing_tools):
    print('Finishing tools:', len(finishing_tools))
    print('{0},{1},{2},{3},{4},{5},{6}'.format(
        'Type','Diameter','Depth','FinishingSideQq','FinishingBottomQq','PremachiningSideQq','PremachingBottomQq'))
    for finishing_tool in finishing_tools:
        process_finishing_tool(finishing_tool)

def process_drilling_tool(tool):
    results = tool['cuttingData']['Results']
    drilling_value = ''
    milling_value = ''
    # print(results)
    if 'DrillingResultElement' in results:
        drilling_value = results['DrillingResultElement']['Vf']
    elif 'MillingResultElement' in results:
        if isinstance(results['MillingResultElement']   , list):
            drilling_value = results['MillingResultElement'][0]['Qq']
        else:
            drilling_value = 0
            if 'Vf' in results['MillingResultElement']:
                drilling_value = results['MillingResultElement']['Vf']
            elif 'Vfm' in results['MillingResultElement']:
                drilling_value = results['MillingResultElement']['Vfm']
            else:
                print(results)

    print('{0},{1},{2},{3}'.format(
        tool['toolType'],
        tool['diameter'],
        tool['depthMax'],
        drilling_value
        ))

def process_drilling_tools(drilling_tools):
    print('Drilling tools:', len(drilling_tools))
    print('{0},{1},{2},{3}'.format(
        'Type','Diameter','Depth','Vf','Qq'))
    for drilling_tool in drilling_tools:
        process_drilling_tool(drilling_tool)

def dump_tools(name):
    milling_filename = '{0}/millingTools.json'.format(name)
    finishing_filename = '{0}/finishingTools.json'.format(name)
    drilling_filename = '{0}/drillingTools.json'.format(name)
    milling_tools = json_file_to_dict(milling_filename)
    finishing_tools = json_file_to_dict(finishing_filename)
    drilling_tools = json_file_to_dict(drilling_filename)
    process_milling_tools(milling_tools)
    process_finishing_tools(finishing_tools)
    process_drilling_tools(drilling_tools)

# dump_tools('H')
# dump_tools('K')
# dump_tools('M')

# dump_tools('N')
# dump_tools('P')
