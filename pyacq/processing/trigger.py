# -*- coding: utf-8 -*-
"""

"""




# debounce_time
# debounce_mode = after_stable    before_stable

"""
CTR_TRIGGER_AFTER_STABLE: This mode rejects glitches and only passes state transitions after a specified period of stability
(the debounce time). This mode is used with electromechanical devices like encoders and mechanical switches to reject switch
bounce and disturbances due to a vibrating encoder that is not otherwise moving. The debounce time should be set short
enough to accept the desired input pulse but longer than the period of the undesired disturbance.
CTR_TRIGGER_BEFORE_STABLE: Use this mode when the input signal has groups of glitches and each group is to be counted
as one. The trigger before stable mode will recognize and count the first glitch within a group but reject the subsequent glitches
within the group if the debounce time is set accordingly. In this case the debounce time should be set to encompass one entire
group of glitches
"""

class AnalogTrigger:
    pass


class DigitalTrigger:
    pass



