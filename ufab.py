#!/usr/bin/env python

import sys
import argparse
import json
import os
import xlsxwriter
import subprocess
import re
import struct
from html import escape

def parse_arguments(arguments):
    parser = argparse.ArgumentParser()
    parser.add_argument('--excel', help='Write an output file', required=True)
    args = vars(parser.parse_args(arguments))
    return args


def usage():
    print('Usage: comparePlans --excel file.xlsx')


def get_operating_system():
    operating_systems = {
        'linux1': 'Linux',
        'linux2': 'Linux',
        'darwin': 'OSX',
        'win32': 'Windows'
    }
    return operating_systems.get(sys.platform, sys.platform)


def prefix_command():
    prefix = []
    # if get_operating_system() == 'Linux':
    #     prefix = ['xvfb-run', '--auto-servernum', '--server-num=99', '--server-args=-screen 0 1024x768x24']
    return prefix


def json_file_to_dict(file_path):
    with open(file_path) as jf1:
        json_string = jf1.read()
        return json.loads(json_string)


def add_to_worksheet(worksheet, column, row, value):
    worksheet.write(column + str(row), value)


def approx_equal(a, b):
    return (abs(b - a) <= 1e-6)


def direction_as_string(direction):
    xRot = direction['xRot']
    yRot = direction['yRot']
    name = ''

    if approx_equal(xRot, 0.0) and approx_equal(yRot, 0.0):
        name = 'TOP'
    if approx_equal(xRot, 180.0) and approx_equal(yRot, 0.0):
        name = 'BOTTOM'
    if approx_equal(xRot, 0.0) and approx_equal(yRot, 90.0):
        name = 'RIGHT'
    if approx_equal(xRot, 0.0) and approx_equal(yRot, -90.0):
        name = 'LEFT'
    if approx_equal(xRot, -90.0) and approx_equal(yRot, 0.0):
        name = 'REAR'
    if approx_equal(xRot, 90.0) and approx_equal(yRot, 0.0):
        name = 'FRONT'
    return '{0} xRot:{1} yRot:{2}'.format(name, xRot, yRot)


def format_time(time, fraction=False):
    time_in_seconds = int(round(time))
    seconds = int(time_in_seconds % 60)
    minutes = int((time_in_seconds / 60) % 60)
    hours = int((time_in_seconds / 60 / 60))
    result = ''
    if hours > 0:
        result += '{0}h'.format(hours)
    if minutes > 0:
        if len(result) > 0:
            result += ' '
        result += '{0}m'.format(minutes)
    if seconds > 0 or len(result) == 0:
        if len(result) > 0:
            result += ' '
        if len(result) == 0 and seconds == 0:
            result += '{0}s'.format(round(time, 3))
        else:
            if fraction:
                result += '{0:.1f}s'.format(time - hours*3600 - minutes*60)
            else:
                result += '{0:.1f}s'.format(seconds)
    return result


def write_plan_output(plans, plan_number, worksheet, column, row_index, output_folder, context, detailed):
    plan = plans[plan_number]
    row_index = row_index + 1
    row_index = row_index + 1
    orig_row_index = row_index

    stage_number = 1
    last_tool = plan['stages'][0]['steps'][0]['toolName']
    setup_times = 0
    operation_times = 0
    stages_output = []
    for stage in plan['stages']:
        row_index, last_tool, stage_info, stage_output = write_stage_output(column, plan, row_index, stage, stage_number, worksheet,
                                                              output_folder, last_tool, context, detailed)
        stages_output.append(stage_output)
        setup_times = setup_times + stage_info['SetupTime']
        operation_times = operation_times + stage_info['OperationTime']
        stage_number = stage_number + 1

    billing_rate = context['MachineBillingRate'] / 3600.0
    machining_cost = operation_times * billing_rate
    setup_cost = setup_times * billing_rate
    # machining_cost = plan['cost']['operation'] + plan['cost']['tooling']
    # setup_cost = plan['setupCost']

    total_cost = machining_cost + setup_cost
    total_time = setup_times + operation_times

    data = 'Plan {0} - [COST Total ${1:,.2f} = Operation ${2:,.2f} + Setup ${3:,.2f}] [TIME Total {4} = Operation {5} + Setup {6}]'.format(
        plan_number + 1,
        round(total_cost, 2),
        round(machining_cost, 2),
        round(setup_cost, 2),
        format_time(total_time, True),
        format_time(operation_times, True),
        format_time(setup_times, True)
    )
    worksheet.write(column + str(orig_row_index - 1), data, header_format)

    plan_output = [data] + stages_output
    return row_index, plan_output


def calculate_stage_time(setup_time, tool_change_time, stage, last_tool):
    stages_time = 0
    tool_changes_time = 0
    for step in stage['steps']:
        if last_tool != step['toolName']:
            tool_changes_time = tool_changes_time + tool_change_time
            last_tool = step['toolName']
        stages_time = stages_time + minutes_to_seconds(step['time'])
    return stages_time, tool_changes_time, last_tool


def write_stage_output(column, plan, row_index, stage, stage_number, worksheet, output_folder, last_tool, context,
                       detailed):
    stage = plan['stages'][stage_number - 1]

    setup_time = context['stageTime']
    load_unload_time = context['LoadUnloadTime']
    tool_change_time = context['ToolChangeTime']

    stages_time, tool_changes_time, last_tool = calculate_stage_time(setup_time, tool_change_time, stage, last_tool)
    stage_time = setup_time + load_unload_time + stages_time + tool_changes_time
    # stage_time = plan['stageTimes'][stage_number - 1]
    data = '    Stage {0} - [TIME Total {1} = Setup {2} + Steps {3} + Load/Unload {4} + Tool Changes {5}] - Direction {6}'.format(
        stage_number,
        format_time(stage_time, True),
        format_time(setup_time, True),
        format_time(stages_time, True),
        format_time(load_unload_time, True),
        format_time(tool_changes_time, True),
        direction_as_string(stage['direction'])
    )

    worksheet.write(column + str(row_index), data, cell_format)
    row_index = row_index + 1
    stepNumber = 1
    steps_output = []
    for step in stage['steps']:
        row_index, step_info, step_output = write_step_output(column, row_index, step, stepNumber, worksheet, output_folder,
                                                 detailed)
        steps_output.append(step_output)
        stepNumber = stepNumber + 1

    stage_info = {
        'StageTime': stage_time,
        'SetupTime': setup_time,
        'OperationTime': load_unload_time + stages_time + tool_changes_time
    }
    stage_output = [data] + steps_output
    # return row_index, last_tool, setup_time, (load_unload_time + stages_time + tool_changes_time)
    return row_index, last_tool, stage_info, stage_output


def write_step_output(column, row_index, step, step_number, worksheet, output_folder, detailed):
    if step['type'] == 'ROUGHING':
        results = json.dumps(step['toolData']['CGRecommendedToolData']['cuttingData']['Results'])
        data = '        Step {0} - Cost ${1:,.3f} - Time {2} - Volume {3:,.0f}mm^3 - {4} - {5}'.format(
            step_number,
            round(step['cost']['operation'], 3),
            format_time(minutes_to_seconds(step['time']), True),
            round(step['volume'] * 1000000 * 1000, 3),
            step['description'],
            step['toolName'])
    if step['type'] == 'FINISHING':
        results = json.dumps(step['toolData']['CGRecommendedToolData']['cuttingData']['Results'])
        data = '        Step {0} - Cost ${1:,.3f} - Time {2} - Area {3:,.0f}mm^2 - {4} - {5}'.format(
            step_number,
            round(step['cost']['operation'], 3),
            format_time(minutes_to_seconds(step['time']), True),
            round(step['area'] * 10000 * 100, 3),
            step['description'],
            step['toolName'])

    output = [data]
    if detailed:
        scale = 4
        worksheet.write(column + str(row_index), data, cell_format)
        row_index = row_index + 1
        worksheet.set_row(row_index - 1, 10 + 60 * scale)
        worksheet.write(column + str(row_index), '            ' + results, cell_small_format)
        output.append(results)
        worksheet.insert_image(column + str(row_index),
                               os.path.join(output_folder, step['Image:']),
                               {'x_offset': 45, 'y_offset': 20, 'x_scale': 0.25 * scale, 'y_scale': 0.25 * scale})
    else:
        worksheet.write(column + str(row_index), data, cell_format)
    row_index = row_index + 1

    step_info = {
        'Time': minutes_to_seconds(step['time']),
        'Cost': step['cost']['operation']
    }
    return row_index, step_info, output


def write_all_plans_output(plans, worksheet, column, row_index, output_folder, context, detailed):
    plans_output = []
    for plan_index in range(0, len(plans)):
        row_index, plan_output = write_plan_output(plans, plan_index, worksheet, column, row_index, output_folder, context, detailed)
        plans_output.append(plan_output)
    return plans_output


def parse_output_bounding_box(output):
    bounding_box_root = json.loads('null')
    matches = re.findall('REPORTING] BoundingBox: \\[.*\\]', output)
    if len(matches) > 0:
        match = matches[0]
        bounding_box = match[match.find("["):]
        bounding_box_root = json.loads(bounding_box)
    return bounding_box_root


def parse_output_material(output):
    material_root = json.loads('null')
    matches = re.findall('REPORTING] Material: \\{.*\\}', output)
    if len(matches) > 0:
        match = matches[0]
        material = match[match.find("{"):]
        material_root = json.loads(material)
    return material_root


def parse_output_machine(output):
    machine_root = json.loads('null')
    matches = re.findall('REPORTING] Machine: \\{.*\\}', output)
    if len(matches) > 0:
        match = matches[0]
        machine = match[match.find("{"):]
        machine_root = json.loads(machine)
    return machine_root


def parse_output(output):
    bounding_box_root = parse_output_bounding_box(output)
    material_root = parse_output_material(output)
    machine_root = parse_output_machine(output)
    result = {
        'BoundingBox': bounding_box_root,
        'Material': material_root,
        'Machine': machine_root
    }
    return result


def compute_part_dimensions(boundingBox):
    part_length = round(boundingBox[0])
    part_width = round(boundingBox[1])
    part_height = round(boundingBox[2])
    part_dimensions = [part_length, part_width, part_height]
    return part_dimensions


def run_kernel(part_full_path_filename, material, query_type, summary_worksheet, comparison_worksheet,
               settings, write_part_summary, column_index):
    settings['Query'] = query_type.upper()
    settings['PartFullPathFilename'] = part_full_path_filename
    settings['PartDirectory'], settings['PartFilename'] = os.path.split(part_full_path_filename)
    settings['PartName'], settings['PartNameExtension'] = os.path.splitext(settings['PartFilename'])

    uniqueid = '{0} {1}'.format(material['tabname'], settings['Query'])
    unique_worksheet_name = truncate_middle(uniqueid, 29)
    unique_folder_name = '{0}-{1}-{2}'.format(settings['PartName'], material['shortname'], settings['Query'])
    output_folder = os.path.join('/tmp/ufab/output', unique_folder_name)

    context = execute_runKernel(material, material['type'], output_folder, settings['PartName'],
                                part_full_path_filename,
                                settings['Query'])
    if context == None:
        return

    context['MachineBillingRate'] = context['Machine']['billingRate($/hr)']
    context['ToolChangeTime'] = context['Machine']['tct']
    context['stageTime'] = context['Machine']['stageTime'] * 60
    context['LoadUnloadTime'] = context['Machine']['loadUnloadTime']
    context['MaterialCost'] = context['Material']['Price per volume ($/m^3']
    # emil

    context.update(settings)

    # print_stl_file(os.path.join(output_folder, 'stl.stl'))

    part_dimensions = compute_part_dimensions(context['BoundingBox'])

    solutions_full_path_filename = os.path.join(output_folder, 'solutions.json')
    solutions_dict = json_file_to_dict(solutions_full_path_filename)
    if not solutions_dict['validPlanExists']:
        print('************ No valid plan exists')
        return

    if write_part_summary:
        write_part_summary_to_worksheet(output_folder, settings['PartName'], part_dimensions,
                                        summary_worksheet)

    messages = []
    title = create_header_messages(context, material, messages, part_dimensions, settings)

    row_index = write_worksheet_header(comparison_worksheet, title, messages)

    row_index = row_index + 1
    comparison_worksheet.write(column_index + str(row_index), 'Query: {0}'.format(settings['Query']), header_format)

    write_all_plans_output(solutions_dict['plans'], comparison_worksheet, column_index, row_index, output_folder,
                           context, False)

    worksheet = workbook.add_worksheet(unique_worksheet_name)
    worksheet.set_column('A:A', column_width)
    row_index = write_worksheet_header(worksheet, title, messages)
    row_index = row_index + 1
    worksheet.write('A' + str(row_index), 'Query: {0}'.format(settings['Query']), header_format)
    plans_output = write_all_plans_output(solutions_dict['plans'], worksheet, 'A', row_index, output_folder, context, True)
    return output_folder, plans_output


def create_header_messages(context, material, messages, part_dimensions, settings):
    title = 'Part: {0}'.format(settings['PartName'])
    material_price_per_meter_squared = context['MaterialCost']
    part_volume = part_dimensions[0] * part_dimensions[1] * part_dimensions[2]
    price_per_part = material_price_per_meter_squared / 1000000000 * part_volume
    messages.append(
        '        Dimensions: {0:,} mm x {1:,} mm x {2:,} mm'.format(int(part_dimensions[0]),
                                                                    int(part_dimensions[1]),
                                                                    int(part_dimensions[2]))
    )
    messages.append('Material: {0}'.format(material['tabname']))
    messages.append('        Price (m^3): ${0:,.2f}'.format(material_price_per_meter_squared))
    messages.append('        Cost Per Part: ${0:,.2f}'.format(price_per_part))
    messages.append(
        'Machine: {0}'.format(context['Machine']['modelId(String)'])
    )
    messages.append('        Billing Rate ${0:,.2f} hr'.format(context['MachineBillingRate']))
    messages.append('        Setup Time: {0}'.format(format_time(context['stageTime'], True)))
    messages.append('        Load/Unload Time: {0}'.format(format_time(context['LoadUnloadTime'], True)))
    messages.append('        Tool Change Time: {0}'.format(format_time(context['ToolChangeTime'], True)))
    messages.append('')
    return title


def write_worksheet_header(worksheet, title, messages):
    worksheet.write('A' + '1', title, title_format)
    row_index = 2
    for message in messages:
        worksheet.write('A' + str(row_index), message, header_format)
        row_index = row_index + 1
    return row_index - 1


def execute_runKernel(material, material_type, output_folder, part_base_name, part_full_path_filename, query_type):
    if (query_type.lower() == 'formula'):
        command = ['./runKernel', '-i', part_full_path_filename, '-f', output_folder, '-q', query_type.lower(),
                   '-m', material['code']]
    else:
        command = ['./runKernel', '-i', part_full_path_filename, '-f', output_folder, '-q', query_type.lower(),
                   '-m', material_type]
    command = prefix_command() + command
    # command = command + ['--tools', 'add']
    print
    ' '.join(command)
    print
    # print('Running part "{0}" with material "{1}" with query "{2}"'.format(part_base_name, material['tabname'],
    #                                                                        query_type))

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    exitcode = proc.returncode
    # print(out[:-1])  # strip off last CR

    if exitcode < 0:
        print('************ Exit code: {0}'.format(exitcode))
        return None

    out = str(out, 'utf-8')
    json = parse_output(out)
    return json


def write_part_summary_to_worksheet(output_folder, part_base_name, part_dimensions,
                                    summary_worksheet):
    scale = 4
    row_index = 1
    data = 'Part: {0}'.format(part_base_name)
    summary_worksheet.write('A' + str(row_index), data, title_format)
    row_index = row_index + 1
    data = 'Dimensions: {0:,} mm x {1:,} mm x {2:,} mm'.format(int(part_dimensions[0]), int(part_dimensions[1]),
                                                               int(part_dimensions[2]))
    summary_worksheet.write('A' + str(row_index), data, header_format)
    row_index = row_index + 1
    summary_worksheet.set_row(row_index - 1, 60 * scale)
    summary_worksheet.insert_image('A' + str(row_index),
                                   os.path.join(output_folder, 'end.png'),
                                   {'x_offset': 5, 'y_offset': 5, 'x_scale': 0.25 * scale,
                                    'y_scale': 0.25 * scale})


def get_files_in_folder(folder):
    for (dirpath, dirnames, filenames) in os.walk(parts_folder):
        return sorted([os.path.join(dirpath, file) for file in filenames])


def truncate_middle(s, n):
    if len(s) <= n:
        return s
    n = n - 3
    end_length = int(n) / 2
    begin_length = n - end_length
    return '{0}...{1}'.format(s[:begin_length], s[-end_length:])


def minutes_to_seconds(n):
    return n * 60


def get_bytes_from_file(filename):
    return open(filename, "rb").read()


def print_stl_file(filename):
    print
    filename, 'bytes'
    bytes = get_bytes_from_file(filename)
    print
    len(bytes)
    # print '{0} {1}'.format(int(bytes[80]), int(bytes[81]))
    number_triangles, = struct.unpack('i', bytes[80:84])
    print
    number_triangles
    offset = 84
    minX = None
    maxX = None
    minY = None
    maxY = None
    minZ = None
    maxZ = None
    for i in range(0, number_triangles):
        n = struct.unpack("<3f", bytes[offset:offset + 12])
        offset = offset + 12
        p1 = struct.unpack("<3f", bytes[offset:offset + 12])
        offset = offset + 12
        p2 = struct.unpack("<3f", bytes[offset:offset + 12])
        offset = offset + 12
        p3 = struct.unpack("<3f", bytes[offset:offset + 12])
        offset = offset + 12
        b = struct.unpack("<h", bytes[offset:offset + 2])
        offset = offset + 2
        # print p1, p2, p3
        if minX == None:
            minX = p1[0]
        minX = min(minX, p1[0], p2[0], p3[0])
        if maxX == None:
            maxX = p1[0]
        maxX = max(maxX, p1[0], p2[0], p3[0])
        if minY == None:
            minY = p1[1]
        minY = min(minY, p1[1], p2[1], p3[1])
        if maxY == None:
            maxY = p1[1]
        maxY = max(maxY, p1[1], p2[1], p3[1])
        if minZ == None:
            minZ = p1[2]
        minZ = min(minZ, p1[2], p2[2], p3[2])
        if maxZ == None:
            maxZ = p1[2]
        maxZ = max(maxZ, p1[2], p2[2], p3[2])
    print
    minX, maxX, minY, maxY, minZ, maxZ


def run_experiment(parts_filenames, materials, query_types, settings, output_folder):
    global workbook, title_format, header_format, cell_format, cell_small_format, column_width

    output_folders = []
    column_width = 120
    for part in parts_filenames:
        # print(part)
        part_directory, part_filename = os.path.split(part)
        part_base_name, part_extension = os.path.splitext(part_filename)
        excel_filename = os.path.join(output_folder, '{}.xlsx'.format(part_base_name))

        # print('\n************ Writing to {0}'.format(excel_filename))

        workbook = xlsxwriter.Workbook(excel_filename)
        title_format = workbook.add_format({'bold': True, 'font_size': 20, 'align': 'top'})
        header_format = workbook.add_format({'bold': True, 'font_size': 12, 'align': 'top'})
        cell_format = workbook.add_format({'bold': False, 'font_size': 10, 'align': 'top'})
        cell_small_format = workbook.add_format({'bold': False, 'font_size': 9, 'align': 'top'})

        write_part_summary = True
        summary_worksheet = workbook.add_worksheet('Summary')
        summary_worksheet.set_column('A:A', column_width)

        for material in materials:
            material_comparison = '{0} Compare'.format(material['tabname'])
            material_comparison = truncate_middle(material_comparison, 31)
            comparison_worksheet = workbook.add_worksheet(material_comparison)
            comparison_worksheet.set_column('A:C', column_width)

            column_index = 'A'
            for query_type in query_types:
                output_folder, plans_output = run_kernel(part, material, query_type, summary_worksheet, comparison_worksheet, settings,
                           write_part_summary, column_index)
                # for plan in plans_output:
                #     print(plan[0].strip())
                #     for i in range(1, len(plan)):
                #         stage = plan[i]
                #         print(stage[0].strip())
                #         for j in range(1, len(stage)):
                #             step = stage[j]
                #             for item in step:
                #                 print(item.strip())
                output_folders.append(output_folder)
                write_part_summary = False
                column_index = chr(ord(column_index) + 1)

        workbook.close()
    return output_folders, plans_output


# arguments = sys.argv[1:]
# args = parse_arguments(arguments)

# parts_folder = 'resources/data/parts/step/parc'
# parts_filenames = get_files_in_folder(parts_folder)
parts_filenames = [
    'resources/data/parts/step/sandvik/BottleOpener_SharperRadius.stp',
    # 'resources/data/parts/step/parc/functional/plate_with_slots_top.step',
    # 'resources/data/parts/step/web/spindleMountBracket.step',
    # 'resources/data/parts/step/web/piusiFlange.step',
    # 'resources/data/parts/step/web/nonWeldedBracket.step',
    # 'resources/data/parts/step/web/vw18turbo.step',
    # 'resources/data/parts/step/web/bellHousing.step',
    # 'resources/data/parts/step/web/j1motorMount.step',
    # 'resources/data/parts/step/web/45x45.step',
    # 'resources/data/parts/step/web/cornerBracket.step',

    # 'resources/data/parts/step/parc/twoParts.step',
    # 'resources/data/parts/step/parc/cubeBlindHole.step',
    # 'resources/data/parts/step/parc/B-Blocky.step',
    # 'resources/data/parts/step/sandvik/BottleOpener_Coin_step_big.stp',
    # 'resources/data/parts/step/mill-test/partWithHole.step',
    # 'resources/data/parts/step/parc/cubeHole.step',
    # 'resources/data/parts/step/parc/cubeInset.step',
    # 'resources/data/parts/step/parc/cube.step',
    # 'resources/data/parts/step/parc/blindHole.step',
    # 'resources/data/parts/step/parc/throughHole.step',
    # 'resources/data/parts/step/sandvik/threaded_hole.step',
    # 'resources/data/parts/step/sandvik/uFab_MT_three_slots.step',
    # 'resources/data/parts/step/parc/part-1.step',
    # 'resources/data/parts/step/sandvik/model3.step',
    # 'resources/data/parts/step/sandvik/model4.step',
    # 'resources/data/parts/step/sandvik/TCG04000043180_A.step',

    # 'resources/data/parts/step/sandvik/Pieza3.step',
    # 'resources/data/parts/step/parc/REAR_HV_MOUNT_LEFT.step',
    # 'resources/data/parts/step/parc/NEMA23MotorMount.step',
    # 'resources/data/parts/step/parc/TCG04000042337_A.step',
    # 'resources/data/parts/step/parc/unreachable.step',
    # 'resources/data/parts/step/parc/CDS-6500-14_large.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-2.0.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-4.0.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-4.5.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-7.5.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-7.54.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-8.3.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-10.3.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-12.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-12.6.step',
    # 'resources/data/parts/step/drill-test/drill-test-H-9x.step',
    # 'resources/data/parts/step/drill-test/drill-test-K-2.0.step',
    # 'resources/data/parts/step/drill-test/drill-test-K-3.1.step',
    # 'resources/data/parts/step/drill-test/drill-test-K-3.2.step',
    # 'resources/data/parts/step/drill-test/drill-test-K-4.7.step',
    # 'resources/data/parts/step/drill-test/mill-and-drill-N.step',
    # 'resources/data/parts/step/drill-test/mill-and-drill-2-N.step',
    # 'resources/data/parts/step/drill-test/mill-and-drill-3-N.step',
    # 'resources/data/parts/step/drill-test/mill-and-drill-4-N.step',
    # 'resources/data/parts/step/drill-test/mill-and-drill-5-N.step',

    # crashing
    # 'resources/data/parts/step/web/tbHousing.step',
    # 'resources/data/parts/step/web/pedestalHousing.step',
    # 'resources/data/parts/step/web/nema34Box.step',
    # 'resources/data/parts/step/web/nema34BoxCover.step',

    # 'resources/data/parts/step/sandvik/DeepChannels.step',
    #
    # 'resources/data/parts/step/parc/nf_TCG04000042345_A.step',
    # 'resources/data/parts/step/parc/hollowCube.step',
    # 'resources/data/parts/step/sandvik/ufab_test_det_1.step',
]

materials = [
    {'name': 'Aluminum (6061) N', 'tabname': 'Aluminum-N1.2.Z.AG', 'shortname': 'alumN', 'type': 'N',
     'code': 'N1.2.Z.AG'},
    {'name': 'Tool Steel (P20) H', 'tabname': 'ToolSteel-H1.1.Z.HA', 'shortname': 'toolSteelH', 'type': 'H',
     'code': 'H1.1.Z.HA'},
    {'name': 'Cast iron (A536) K', 'tabname': 'CastIron-K3.2.C.UT', 'shortname': 'ironK', 'type': 'K',
     'code': 'K3.2.C.UT'},
    {'name': 'Stainless steel (304) M', 'tabname': 'StainlessSteel-M1.0.Z.AQ', 'shortname': 'stainlessM', 'type': 'M',
     'code': 'M1.0.Z.AQ'},
    {'name': 'Steel (4140) P', 'tabname': 'Steel-P1.1.Z.AN', 'shortname': 'steelP', 'type': 'P', 'code': 'P1.1.Z.AN'},
]

query_types = [
    'formula',
    # 'json',
    # 'tguide'
]

settings = {
}

def run_part(part_filename, material_requested, query):
    for material in materials:
        if material['type'] == material_requested:
            material_input = [material]
    return run_experiment([part_filename], material_input, [query], {}, '/tmp')

# run_experiment(parts_filenames, materials, query_types, settings)


def html_header():
    return '''
<!DOCTYPE html>
<html>
<body>'''

def html_footer():
    return '''
</body>
</html>'''

def html_summary(folder, excel_filename):
    html = '<h1>Part ' + folder + '</h1>'
    url = "file/" + folder + '/' + 'end.png'
    html = html + '<img src="' + url + '" >\n'

    url = "preview/" + folder + '/' + 'voxpart.stl'
    html = html + '&nbsp;&nbsp;&nbsp;<a href="' + url + '" target="_blank" >Preview</a>'

    url = "file/" + folder + '/' + excel_filename
    html = html + '&nbsp;&nbsp;&nbsp;<a href="' + url + '" >Download Excel</a>'
    return html

def html_space(n):
    html = ''
    for i in range(0, n):
        html = html + '&nbsp;'
    return html

def html_step(folder, step, step_output):
    html = '<p style="font-size:80%;">' + html_space(8) + escape(step_output[0].strip()) + '</p>'
    if len(step_output) > 1:
        html = html + '<p style="font-size:80%;">' + html_space(12) + step_output[1].strip() + '</p>'
    step_image = step['Image:']
    step_remaining_volue = step['Remaining volume STL file:']
    step_removal_volue = step['Removal volume STL file:']
    url = "file/" + folder + '/' + step_image
    html = html + '<img src="' + url + '" >'
    url = "preview/" + folder + '/' + step_removal_volue
    html = html + '&nbsp;&nbsp;&nbsp;<a href="' + url + '" target="_blank" >Removal Volume</a>'
    url = "preview/" + folder + '/' + step_remaining_volue
    html = html + '&nbsp;&nbsp;&nbsp;<a href="' + url + '" target="_blank" >Remaining Volume</a>'
    return html

def html_stage(folder, stage, stage_output):
    html = '<p style="font-size:90%;">' + html_space(4) + stage_output[0].strip() + '</p>\n'
    stepIndex = 0
    for step in stage['steps']:
        html = html + html_step(folder, step, stage_output[stepIndex + 1])
        stepIndex = stepIndex + 1
    return html

def html_plan(folder, plan, plan_output):
    html = '<p style="font-size:110%;">' + plan_output[0].strip() + '</p>\n'
    stageIndex = 0
    for stage in plan['stages']:
        html = html + html_stage(folder, stage, plan_output[stageIndex + 1])
        stageIndex = stageIndex + 1
    return html

def generate_html(folder, plans_output, excel_filename):
    solutions_file = os.path.join(folder, 'solutions.json')
    folder_basename = os.path.basename(folder)
    with open(solutions_file) as json_file:
        data = json.load(json_file)
        html = html_header()
        html = html + html_summary(folder_basename, excel_filename)
        if data['validPlanExists']:
            planIndex = 0
            for plan in data['plans']:
                html = html + html_plan(folder_basename, plan, plans_output[planIndex])
                planIndex = planIndex + 1
        html = html + html_footer()
        return html
