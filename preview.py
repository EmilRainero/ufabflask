import os
import json

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

def html_header():
    return '''
<!DOCTYPE html>
<html>
<body>'''

def html_footer():
    return '''
</body>
</html>'''

def html_summary():
    return '''
<h1>Part Emil</h1>
<img src="foo.png" />
'''

def html_step(step):
    html = '\t\t<h4>Step</h4>\n'

    return html

def html_stage(stage):
    html = '\t<h3>Stage</h3>\n'
    for step in stage['steps']:
        html = html + html_step(step)
    return html

def html_plan(plan):
    html = '<h2>Plan</h2>\n'
    for stage in plan['stages']:
        html = html + html_stage(stage)
    return html

def generate_html(filename):
    with open(solutions_file) as json_file:
        data = json.load(json_file)
        html = html_header()
        html = html + html_summary()
        if data['validPlanExists']:
            for plan in data['plans']:
                html = html + html_plan(plan)
        html = html + html_footer()
        return html

folder = '/tmp/ufab/output/threeslots-alumN-JSON'
solutions_file = os.path.join(folder, 'solutions.json')

print(generate_html(solutions_file))

    # stream << "<img src=\"" << directory << "/end.png" << "\" />" << std::endl;
    #
    # std::string
    # htmlFile, url;
    # std::string
    # filename;
    #
    # htmlFile = Path::join(FilesystemUtils::getCurrentDirectory(), "resources", "data", "html", "ufab.html");
    # filename = directory + "/voxpart.stl";
    # url = "file://" + htmlFile + "?file=" + filename;
    # stream << R"(<button class="
    # btn
    # btn - success
    # " onclick="
    # window.open(')" << url
    #             << "','_blank')\">Part in voxel</button>" << std::endl;
    #
    # if (root["validPlanExists"].asBool()) {
    # for (int i = 0; i < root["plans"].size(); i++) {
    # planToHtml(root["plans"][i], i, stream, directory);
    # }
    # }
    #
    # stream << "</body>" << std::
    #     endl;
    # stream << "</html>" << std::endl;