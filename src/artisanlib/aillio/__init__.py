if __name__ == "__main__":
    import bullet_r1
    import logging
    logger = logging.getLogger('artisian')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    R1 = BulletR1(logger)
    R1.on()
    R1.sample()
