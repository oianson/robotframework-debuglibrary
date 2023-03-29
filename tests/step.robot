*** Settings ***
Library     RobotDebug

*** Test Cases ***
test1
    debug
    High    hello    world
    High    Next     High
    log to console  working
    @{list} =  Create List    hello    world
    debug
    Log Many    @{list}

test2
    log to console  another test case
    debug
    log to console  end

*** Keywords ***
High
    [Arguments]    ${arg}   ${arg2}
    middle  ${arg}
    middle  ${arg2}

middle
    [Arguments]    ${arg}
    low  ${arg}

low
    [Arguments]    ${arg}
    log to console  ${arg}