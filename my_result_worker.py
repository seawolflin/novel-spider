from pyspider.result import ResultWorker
import logging
import pymongo

logger = logging.getLogger("result")


class MongoDBResultWorker(ResultWorker):
    def on_result(self, task, result):
        """
        Called every result
        """
        if not result:
            return
        if 'taskid' in task and 'project' in task and 'url' in task:
            logger.info('result %s:%s %s -> %r' % (
                task['project'], task['taskid'], task['url'], result))
            if not isinstance(result, list):
                result = [result]

            client = pymongo.MongoClient(host='localhost', port=27017)
            db = client['spider_novels']
            coll = db['novels']

            logger.info('update %d datas' % len(result))
            for item in result:
                if 'url' in item:
                    item["source"] = task['project']
                    data_id = coll.update({'url': item['url']}, {"$set": item}, upsert=True)
                    logger.info(data_id)
        else:
            logger.warning('result UNKNOW -> %r' % result)
            return
