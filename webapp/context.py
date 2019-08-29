# Standard library
import copy
import datetime
import calendar
import logging
import json

# Packages
import flask
import yaml
import dateutil.parser
from canonicalwebteam.http import CachedSession


logger = logging.getLogger(__name__)

api_session = CachedSession(fallback_cache_duration=3600)


def _get(url):
    try:
        response = api_session.get(url, timeout=10)
        response.raise_for_status()
    except Exception as request_error:
        logger.debug(
            "Attempt to get feed failed: {}".format(str(request_error))
        )
        return False

    return response


# Read navigation.yaml
with open("navigation.yaml") as navigation_file:
    nav_sections = yaml.load(navigation_file.read(), Loader=yaml.FullLoader)


# Process data from YAML files
# ===


def releases():
    """
    Read releases as a dictionary from releases.yaml,
    and provide the contents as a dictionary in the global
    template context
    """

    with open("releases.yaml") as releases:
        return yaml.load(releases, Loader=yaml.FullLoader)


def _remove_hidden(pages):
    filtered_pages = []

    # Filter out hidden pages
    for child in pages:
        if not child.get("hidden"):
            filtered_pages.append(child)

    return filtered_pages


def navigation(path):
    """
    Set "nav_sections" and "breadcrumbs" dictionaries
    as global template variables
    """

    breadcrumbs = {}

    is_topic_page = path.startswith("/blog/topics/")

    sections = copy.deepcopy(nav_sections)

    for nav_section_name, nav_section in sections.items():
        # Persist parent navigation on child pages in certain cases
        if nav_section.get("persist") and path.startswith(nav_section["path"]):
            breadcrumbs["section"] = nav_section
            breadcrumbs["children"] = nav_section.get("children", [])

        for child in nav_section["children"]:
            if is_topic_page and child["path"] == "/blog/topics":
                # always show "Topics" as active on child topic pages
                child["active"] = True
                break
            elif child["path"] == path:
                child["active"] = True
                nav_section["active"] = True
                breadcrumbs["section"] = nav_section

                grandchildren = breadcrumbs["grandchildren"] = _remove_hidden(
                    child.get("children", [])
                )

                # Build up siblings
                if child.get("hidden") or grandchildren:
                    # Hidden nodes appear alone
                    breadcrumbs["children"] = [child]
                else:
                    # Otherwise, include all siblings
                    breadcrumbs["children"] = _remove_hidden(
                        nav_section.get("children", [])
                    )
                break
            else:
                for grandchild in child.get("children", []):
                    if grandchild["path"] == path:
                        grandchild["active"] = True
                        nav_section["active"] = True
                        breadcrumbs["section"] = nav_section
                        breadcrumbs["children"] = [child]

                        if grandchild.get("hidden"):
                            # Hidden nodes appear alone
                            breadcrumbs["grandchildren"] = [grandchild]
                        else:
                            # Otherwise, include all siblings
                            breadcrumbs["grandchildren"] = _remove_hidden(
                                child.get("children", [])
                            )
                        break

    return {"nav_sections": sections, "breadcrumbs": breadcrumbs}


# Helper functions
# ===


def current_year():
    return datetime.datetime.now().year


def format_date(datestring):
    date = dateutil.parser.parse(datestring)
    return date.strftime("%-d %B %Y")


def build_path_with_params():
    query_params = flask.request.args.copy()
    query_string = "?"

    if "page" in query_params:
        query_params.pop("page")

    if len(query_params) > 0:
        query_string += query_params.urlencode()

    return flask.request.path + query_string


def months_list(year):
    months = []
    now = datetime.datetime.now()
    for i in range(1, 13):
        date = datetime.date(year, i, 1)
        if date < now.date():
            months.append({"name": date.strftime("%b"), "number": i})
    return months


def month_name(string):
    month = int(string)
    return calendar.month_name[month]


def descending_years(end_year):
    now = datetime.datetime.now()
    return range(now.year, end_year, -1)


def get_json_feed(url, offset=0, limit=None):
    """
    Get the entries in a JSON feed
    """

    end = limit + offset if limit is not None else None

    response = _get(url)

    try:
        content = json.loads(response.text)
    except json.JSONDecodeError as parse_error:
        logger.warning(
            "Failed to parse feed from {}: {}".format(url, str(parse_error))
        )
        return False

    return content[offset:end]
