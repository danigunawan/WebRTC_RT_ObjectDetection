
OBJECT_DETECTION_TASK_TYPE = 'OBJECT_DETECTION'

# Classe Machine Learning Unit Work: model a unit work for a machine learning task
class ML_UnitWork:
    def __init__(self, taskType, data, taskConfig=None, taskIdentifier=None):
        self.taskType = taskType
        self.data = data
        self.taskConfig = taskConfig
        self.taskIdentifier = taskIdentifier
    
    def __str__(self):
        return 'taskType: {taskType}, data: {data},  taskConfig: {taskConfig},  taskIdentifier: {taskIdentifier}'.format(taskType=str(self.taskType), data=str(self.data), taskConfig=str(self.taskConfig), taskIdentifier=str(self.taskIdentifier) )