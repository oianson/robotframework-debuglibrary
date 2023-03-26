*** Settings ***
Library     RobotDebug

*** Test Cases ***
test1
    debug
    log to console  working
    @{list} =  Create List    hello    world
    Log Many    @{list}

test2
    log to console  another test case
    log to console  end
