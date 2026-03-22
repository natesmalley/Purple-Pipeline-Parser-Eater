function processEvent(event)
    if event == nil then
        return {}
    end
    event.abc = "abc"
    return event
end